"""Anonymous self-hosted AutoRSE evaluation API; one ASGI process/one scorer."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sqlite3
import time
import unicodedata

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth import Visitors, VisitorLimit, VISITOR_COOKIE, SESSION_SECONDS
from .engine import Engine, MAX_BUNDLE_BYTES, Rejected


def submission_name(value):
    if not isinstance(value, str):
        raise ValueError()
    value = unicodedata.normalize("NFC", value).strip()
    if (not 1 <= len(value) <= 80 or any(unicodedata.category(c).startswith("C") for c in value)):
        raise ValueError()
    return value


def create_app(*, engine=None, visitors=None, start_worker=True):
    if engine is None:
        engine = Engine(os.environ.get("AUTORSE_STATE_DIR", "/var/lib/autorse/state"),
            os.environ.get("AUTORSE_RUNTIME_DIR", "/opt/autorse/current/runtime"),
            os.environ.get("AUTORSE_PRIVATE_DIR", "/var/lib/autorse/private"),
            os.environ.get("AUTORSE_SIGNING_KEY_FILE", "/var/lib/autorse/secrets/receipt.key"),
            os.environ.get("AUTORSE_PRIVATE_MANIFEST_SHA256", ""))
    if visitors is None:
        path = Path(os.environ.get("AUTORSE_SESSION_SECRET_FILE", "/var/lib/autorse/secrets/session.key"))
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError("Session key must be an owner-only regular file")
        secret = path.read_bytes()
        if len(secret) < 32 or len(secret) > 1024:
            raise ValueError("Session key must contain at least 32 random bytes")
        visitors = Visitors(engine.database, os.environ.get("AUTORSE_PUBLIC_ORIGIN", ""), secret=secret)

    @asynccontextmanager
    async def lifespan(app):
        engine.initialize()
        if start_worker:
            engine.start()
        yield
        engine.close()

    app = FastAPI(title="AutoRSE Evaluation", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.engine, app.state.visitors = engine, visitors
    uploads = asyncio.Semaphore(2)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def visitor(request):
        try:
            session = visitors.session(request.cookies.get(VISITOR_COOKIE))
        except sqlite3.Error:
            raise HTTPException(503, "Submission sessions are temporarily unavailable. Please try again later.") from None
        if not session:
            raise HTTPException(401, "Open the evaluation page to initialize this browser's submission session.")
        return session

    def csrf(request, session):
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(supplied, session["csrf"]):
            raise HTTPException(403, "Request verification failed. Reload this page.")
        if request.headers.get("origin") not in (None, visitors.origin):
            raise HTTPException(403, "Request origin does not match this service.")

    def owner_job(job_id, session):
        job = engine.get(job_id, session["subject"])
        if not job:
            raise HTTPException(404, "Evaluation not found.")
        return job

    @app.get("/healthz")
    def health():
        return JSONResponse({"status": "ready" if engine.ready else "initializing",
                             "scoring_ready": engine.ready, "key_id": engine.key_id},
                            status_code=200 if engine.ready else 503)

    @app.get("/api/me")
    def me(request: Request):
        try:
            session = visitors.session(request.cookies.get(VISITOR_COOKIE))
            token = None
            if not session:
                token, session = visitors.new(request.client.host)
        except VisitorLimit:
            raise HTTPException(429, "New submission sessions are temporarily limited. Please try again later.") from None
        except (ValueError, AttributeError):
            raise HTTPException(400, "Client address could not be verified.") from None
        except sqlite3.Error:
            raise HTTPException(503, "Submission sessions are temporarily unavailable. Please try again later.") from None
        response = JSONResponse({"participant_kind": "anonymous-session", "csrf": session["csrf"],
                "scoring_ready": engine.ready, "daily_limit": engine.daily_limit,
                "max_upload_bytes": MAX_BUNDLE_BYTES})
        if token:
            response.set_cookie(VISITOR_COOKIE, token, max_age=SESSION_SECONDS, secure=True,
                                httponly=True, samesite="lax", path="/")
        return response

    @app.get("/api/evaluations")
    def history(request: Request):
        return {"evaluations": engine.recent(visitor(request)["subject"])}

    @app.post("/api/evaluations", status_code=202)
    async def submit(request: Request):
        session = visitor(request)
        csrf(request, session)
        if not engine.ready:
            raise HTTPException(503, "The evaluator is not ready.")
        try:
            display_name = submission_name(request.query_params.get("display_name"))
        except ValueError:
            raise HTTPException(400, "Enter a submission name containing 1–80 characters without control characters.") from None
        try:
            ip_hash = visitors.ip_hash(request.client.host)
        except (ValueError, AttributeError):
            raise HTTPException(400, "Client address could not be verified.") from None
        if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/zip":
            raise HTTPException(415, "Send the six-task ZIP as the request body.")
        size = request.headers.get("content-length")
        if size is not None:
            try:
                if not 0 < int(size) <= MAX_BUNDLE_BYTES:
                    raise ValueError()
            except ValueError:
                raise HTTPException(413, "ZIP must be nonempty and no larger than 512 MiB.") from None
        if uploads.locked():
            raise HTTPException(429, "Two uploads are already in progress. Try again shortly.")
        async with uploads:
            try:
                job, path = engine.reserve(session["subject"], session["participant"],
                                           display_name=display_name, ip_hash=ip_hash)
            except Rejected as error:
                raise HTTPException(429, str(error)) from None
            received, started = 0, time.monotonic()
            try:
                with path.open("xb") as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    iterator = request.stream().__aiter__()
                    while True:
                        try:
                            chunk = await asyncio.wait_for(iterator.__anext__(), timeout=60)
                        except StopAsyncIteration:
                            break
                        received += len(chunk)
                        if received > MAX_BUNDLE_BYTES or time.monotonic() - started > 1800:
                            raise HTTPException(413, "ZIP is too large or upload took too long.")
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                if not received or (size is not None and received != int(size)):
                    raise HTTPException(400, "The upload was incomplete.")
                engine.uploaded(job)
                return {"evaluation_id": job, "status": "queued", "status_url": "/api/evaluations/" + job}
            except BaseException as error:
                engine.fail(job, "Upload did not complete. Please submit again.")
                if isinstance(error, (HTTPException, asyncio.CancelledError)):
                    raise
                raise HTTPException(400, "Upload did not complete. Please submit again.") from None

    @app.get("/api/evaluations/{job_id}")
    def status(job_id: str, request: Request):
        return owner_job(job_id, visitor(request))

    @app.get("/api/evaluations/{job_id}/receipt")
    def receipt(job_id: str, request: Request):
        job = owner_job(job_id, visitor(request))
        if job["status"] != "complete" or not job.get("receipt"):
            raise HTTPException(409, "The evaluation is not complete.")
        return Response(json.dumps(job["receipt"], indent=2, allow_nan=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="evaluation-{job["id"]}.json"'})

    static = Path(__file__).parent / "static"

    @app.get("/evaluate/", include_in_schema=False)
    def page():
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/evaluate-assets", StaticFiles(directory=static), name="evaluate-assets")
    return app
