"""Opaque anonymous visitor sessions; no externally verified account identity."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import hmac
import ipaddress
import secrets
import sqlite3
import time
from urllib.parse import urlsplit
import uuid

VISITOR_COOKIE = "__Host-autorse-visitor"
SESSION_SECONDS = 30 * 24 * 3600
MAX_ACTIVE_VISITORS = 10000
MAX_VISITORS_PER_IP_HOUR = 20


class VisitorLimit(Exception):
    pass


def validate_origin(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ValueError("AUTORSE_PUBLIC_ORIGIN must be an HTTPS origin")
    return value.rstrip("/")


class Visitors:
    def __init__(self, database, origin: str, *, secret: bytes, clock=time.time):
        self.database, self.origin = str(database), validate_origin(origin)
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("A random session secret of at least 32 bytes is required")
        self.secret, self.clock = secret, clock
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS anonymous_visitors (
                token_hash TEXT PRIMARY KEY, subject TEXT NOT NULL UNIQUE,
                participant TEXT NOT NULL UNIQUE, csrf TEXT NOT NULL,
                created INTEGER NOT NULL, expires INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS visitor_creation_limits (
                ip_hash TEXT NOT NULL, hour INTEGER NOT NULL, count INTEGER NOT NULL,
                PRIMARY KEY(ip_hash,hour))""")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def hash(self, value: str, domain=b"visitor"):
        return hmac.new(self.secret, domain + b"\x00" + value.encode(), hashlib.sha256).hexdigest()

    def session(self, token):
        if not isinstance(token, str) or not 0 < len(token) <= 256:
            return None
        with self.db() as db:
            row = db.execute("SELECT subject,participant,csrf,expires FROM anonymous_visitors WHERE token_hash=? AND expires>?",
                             (self.hash(token), int(self.clock()))).fetchone()
        return dict(row) if row else None

    def new(self, address):
        token, subject, csrf = secrets.token_urlsafe(48), uuid.uuid4().hex, secrets.token_urlsafe(32)
        participant = "anonymous-" + uuid.uuid4().hex
        now = int(self.clock())
        hour, ip_hash = now // 3600, self.ip_hash(address)
        with self.db() as db:
            # The caps and inserts share one write transaction, including under
            # concurrent requests from clients that deliberately discard cookies.
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM anonymous_visitors WHERE expires<=?", (now,))
            db.execute("DELETE FROM visitor_creation_limits WHERE hour<?", (hour,))
            count = db.execute("SELECT count FROM visitor_creation_limits WHERE ip_hash=? AND hour=?",
                               (ip_hash, hour)).fetchone()
            if count and count[0] >= MAX_VISITORS_PER_IP_HOUR:
                raise VisitorLimit("New submission sessions are temporarily limited. Please try again later.")
            if db.execute("SELECT COUNT(*) FROM anonymous_visitors").fetchone()[0] >= MAX_ACTIVE_VISITORS:
                raise VisitorLimit("New submission sessions are temporarily limited. Please try again later.")
            db.execute("INSERT INTO anonymous_visitors VALUES (?,?,?,?,?,?)",
                       (self.hash(token), subject, participant, csrf, now, now + SESSION_SECONDS))
            db.execute("""INSERT INTO visitor_creation_limits VALUES (?,?,1)
                       ON CONFLICT(ip_hash,hour) DO UPDATE SET count=count+1""", (ip_hash, hour))
        return token, self.session(token)

    def ip_hash(self, address):
        # Only use the ASGI client's address after the explicitly trusted reverse proxy.
        # Never read X-Forwarded-For or other visitor-supplied headers here.
        canonical = str(ipaddress.ip_address(address))
        return self.hash(canonical, b"ip-quota")
