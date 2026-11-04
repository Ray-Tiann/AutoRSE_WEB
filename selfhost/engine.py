"""One durable scoring queue; uploaded predictions never become executable code."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

MAX_BUNDLE_BYTES = 512 * 1024**2
MAX_QUEUE = 16
IP_DAILY_LIMIT = 20
TASK_ORDER = ("hstu", "intsr", "tiger", "onetrans", "rankmixer", "wukong")
BACKEND = "numpy-cpu-v1"
DEMO_PREDICTIONS = {
    "hstu": "3bbb86f438cb2a77081028bc75cbc0e4a3fc86dc418067d19546518620c98d7a",
    "tiger": "3bbb86f438cb2a77081028bc75cbc0e4a3fc86dc418067d19546518620c98d7a",
    "intsr": "d18117ca4eed9db80a06d4c5358c9672806e9acdb2657a8f681d550f4451875d",
    "onetrans": "81a46c15d8d86b22a966265d94f9587e1966238a954990ff92e68909d90a03cf",
    "rankmixer": "82369010935393434f3b46e51b0abfeebe059be50f180ea22fbf15d6f0d3fe12",
    "wukong": "ae6811294e87d44a10d2d6ee05982f5d1dee045fdb7193e8e9d7b9fb588a94d4"}


class Rejected(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_runtime(runtime):
    for path in (Path(runtime), Path(runtime) / "space"):
        value = str(path.resolve())
        if value not in sys.path:
            sys.path.insert(0, value)
    return (importlib.import_module("service"), importlib.import_module("batch_submission"),
            importlib.import_module("autorse.tasks"), importlib.import_module("autorse.release"))


def verify_private(runtime, private_root, expected_manifest):
    """Verify bytes and inventory; never parse private target values."""
    service, _, _, release = load_runtime(runtime)
    root = Path(private_root).resolve()
    path = root / "private-manifest.json"
    if not expected_manifest or len(expected_manifest) != 64 or sha256(path) != expected_manifest:
        raise ValueError("Private manifest is not pinned")
    manifest = json.loads(path.read_text())
    if manifest.get("public_bundle_sha256") != release.PUBLIC_BUNDLE_SHA256:
        raise ValueError("Private evaluator revision mismatch")
    rows = manifest["files"]
    expected = {f"{task}/{rel}" for task, files in service.PRIVATE_FILES.items() for rel in files}
    actual = {row["path"] for row in rows}
    if actual != expected or len(actual) != len(rows):
        raise ValueError("Private evaluator inventory mismatch")
    for row in rows:
        target = root / row["path"]
        if (target.is_symlink() or not target.resolve().is_relative_to(root)
                or not target.is_file() or target.stat().st_size != row["size"]
                or sha256(target) != row["sha256"]):
            raise ValueError("Private evaluator integrity check failed")


def code_sha(runtime):
    digest = hashlib.sha256()
    for label, base in (("selfhost", Path(__file__).parent), ("runtime", Path(runtime))):
        for path in sorted(base.rglob("*.py")):
            if "tests" in path.parts:
                continue
            digest.update((label + "/" + path.relative_to(base).as_posix()).encode() + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def score_bundle(runtime, private_root, bundle, work):
    service, batch, tasks, release = load_runtime(runtime)
    predictions = batch.unpack_submission_bundle(Path(bundle), Path(work) / "predictions")
    results = {}
    for task in TASK_ORDER:
        result = service.score_submission(task, predictions[task], private_root=Path(private_root))
        result["backend"] = BACKEND
        if (result.get("task") != task or result.get("data_revision") != release.DATA_REVISION
                or result.get("public_bundle_sha256") != release.PUBLIC_BUNDLE_SHA256
                or result.get("submission_sha256") != sha256(predictions[task])
                or result.get("metric") != tasks.TASKS[task]["metric"]):
            raise ValueError("Scoring contract mismatch")
        metric = result.get("metrics", {}).get(result["metric"])
        if type(metric) not in (int, float) or not math.isfinite(metric):
            raise ValueError("Scoring result invalid")
        results[task] = result
    return {"results": results, "data_revision": release.DATA_REVISION,
            "public_bundle_sha256": release.PUBLIC_BUNDLE_SHA256}


def worker_main(argv):
    import resource
    runtime, private_root, bundle, output, work = argv
    resource.setrlimit(resource.RLIMIT_AS, (6 * 1024**3, 6 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (1100, 1100))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**3, 1024**3))
    try:
        payload = score_bundle(runtime, private_root, bundle, work)
        with Path(output).open("x", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(payload, stream, allow_nan=False)
        return 0
    except Exception:
        return 1


class Engine:
    def __init__(self, state, runtime, private_root, signing_key_file, manifest_sha, *,
                 daily_limit=5, runner=None, clock=time.time):
        self.state = Path(state).resolve()
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.state.chmod(0o700)
        self.uploads = self.state / "uploads"
        self.uploads.mkdir(mode=0o700, exist_ok=True)
        self.database = self.state / "autorse.sqlite3"
        self.runtime, self.private_root = Path(runtime).resolve(), Path(private_root).resolve()
        self.signing_key_file, self.manifest_sha = Path(signing_key_file), manifest_sha
        self.daily_limit, self.runner, self.clock = daily_limit, runner, clock
        self.key = None
        self.key_id = None
        self.public_key = None
        self.ready = False
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, subject TEXT NOT NULL, username TEXT NOT NULL,
                    day INTEGER NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
                    status TEXT NOT NULL, error TEXT, receipt TEXT);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
            for name in ("display_name", "ip_hash", "participant_kind"):
                if name not in columns:
                    db.execute(f"ALTER TABLE jobs ADD COLUMN {name} TEXT")
        self.database.chmod(0o600)

    def db(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        try:
            mode = stat.S_IMODE(self.signing_key_file.stat().st_mode)
            if self.signing_key_file.is_symlink() or mode & 0o077:
                raise ValueError()
            self.key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(
                self.signing_key_file.read_text().strip(), validate=True))
            raw = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            self.public_key = base64.b64encode(raw).decode()
            self.key_id = "autorse-" + hashlib.sha256(raw).hexdigest()[:16]
            if self.runner is None:
                verify_private(self.runtime, self.private_root, self.manifest_sha)
            self.evaluator_sha = code_sha(self.runtime)
            self.ready = True
        except Exception:
            self.ready = False
            self.key = None
        return self.ready

    def start(self):
        with self.db() as db:
            # A process restart never silently reuses a partially completed score.
            db.execute("UPDATE jobs SET status='failed',error=?,updated=? WHERE status IN ('running','uploading')",
                       ("Evaluation interrupted. Please submit again.", utcnow()))
            db.execute("""UPDATE jobs SET status='failed',error=?,updated=? WHERE status='queued'
                       AND (participant_kind IS NULL OR participant_kind!='anonymous-session')""",
                       ("This evaluation predates the anonymous submission service. Please submit again.", utcnow()))
        self.cleanup()
        self.thread = threading.Thread(target=self.loop, name="autorse-single-scorer", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=3)

    def reserve(self, subject, username, *, display_name=None, ip_hash=None):
        if not self.ready:
            raise Rejected("The evaluator is not ready.")
        if (not re.fullmatch(r"anonymous-[0-9a-f]{32}", username)
                or not isinstance(display_name, str) or not 1 <= len(display_name) <= 80
                or any(unicodedata.category(c).startswith("C") for c in display_name)):
            raise Rejected("Invalid anonymous submission metadata.")
        if shutil.disk_usage(self.state).free < 2 * 1024**3:
            raise Rejected("The scoring queue is temporarily full.")
        day, job = int(self.clock() // 86400), uuid.uuid4().hex
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute("SELECT COUNT(*) FROM jobs WHERE subject=? AND day=?", (subject, day)).fetchone()[0]
            if used >= self.daily_limit:
                raise Rejected("Daily complete-evaluation limit reached.")
            if ip_hash:
                address_used = db.execute("SELECT COUNT(*) FROM jobs WHERE ip_hash=? AND day=?", (ip_hash, day)).fetchone()[0]
                if address_used >= IP_DAILY_LIMIT:
                    raise Rejected("Daily network evaluation limit reached. Please try again tomorrow.")
            waiting = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('uploading','queued','running')").fetchone()[0]
            if waiting >= MAX_QUEUE:
                raise Rejected("The scoring queue is temporarily full.")
            db.execute("""INSERT INTO jobs
                       (id,subject,username,day,created,updated,status,error,receipt,display_name,ip_hash,participant_kind)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (job, subject, username, day, utcnow(), utcnow(), "uploading", None, None,
                        display_name, ip_hash, "anonymous-session"))
        path = self.uploads / job
        path.mkdir(mode=0o700)
        return job, path / "submission.zip"

    def uploaded(self, job):
        with self.db() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job,)).fetchone()
            if not row or row["status"] != "uploading":
                raise Rejected("Upload could not be queued.")
            db.execute("UPDATE jobs SET status='queued',updated=? WHERE id=?", (utcnow(), job))
        self.wake.set()

    def fail(self, job, message="The prediction ZIP could not be evaluated. Check its format and task identities."):
        with self.db() as db:
            db.execute("UPDATE jobs SET status='failed',error=?,updated=? WHERE id=?", (message, utcnow(), job))
        self.remove_upload(job)

    def remove_upload(self, job):
        if len(job) == 32 and all(c in "0123456789abcdef" for c in job):
            path = self.uploads / job
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)

    def cleanup(self):
        with self.db() as db:
            complete = [r[0] for r in db.execute("SELECT id FROM jobs WHERE status IN ('complete','failed')")]
        for job in complete:
            self.remove_upload(job)

    def get(self, job, subject=None, *, admin=False):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
        if not row or (not admin and row["subject"] != subject):
            return None
        result = {key: row[key] for key in ("id", "display_name", "created", "updated", "status", "error")}
        if row["receipt"]:
            result["receipt"] = json.loads(row["receipt"])
        return result

    def recent(self, subject=None, *, admin=False):
        with self.db() as db:
            if admin:
                rows = db.execute("SELECT id FROM jobs ORDER BY created DESC LIMIT 100").fetchall()
            else:
                rows = db.execute("SELECT id FROM jobs WHERE subject=? ORDER BY created DESC LIMIT 100", (subject,)).fetchall()
        return [self.get(row[0], subject, admin=admin) for row in rows]

    def make_receipt(self, result, job, batch_hash):
        if (job.get("participant_kind") != "anonymous-session"
                or not re.fullmatch(r"anonymous-[0-9a-f]{32}", job["username"])
                or not isinstance(job.get("display_name"), str) or not 1 <= len(job["display_name"]) <= 80):
            raise ValueError("Invalid anonymous receipt metadata")
        results = result["results"]
        if set(results) != set(TASK_ORDER):
            raise ValueError()
        for task in TASK_ORDER:
            item = results[task]
            if (item.get("task") != task or item.get("backend") != BACKEND
                    or item.get("data_revision") != result["data_revision"]
                    or item.get("public_bundle_sha256") != result["public_bundle_sha256"]):
                raise ValueError()
            score = item.get("metrics", {}).get(item.get("metric"))
            if type(score) not in (int, float) or not math.isfinite(score):
                raise ValueError()
        payload = {"schema_version": 1, "status": "complete", "complete": True,
                   "participant": job["username"], "evaluation_id": job["id"],
                   "participant_kind": "anonymous-session", "display_name": job["display_name"],
                   "evaluated_at": utcnow(), "task_count": 6, "task_order": list(TASK_ORDER),
                   "data_revision": result["data_revision"], "public_bundle_sha256": result["public_bundle_sha256"],
                   "batch_sha256": batch_hash, "evaluator_code_sha256": self.evaluator_sha,
                   "backend": BACKEND, "tasks": results,
                   "usage": "demo" if any(results[t].get("submission_sha256") == DEMO_PREDICTIONS[t]
                                               for t in TASK_ORDER) else "benchmark"}
        canonical = b"AutoRSE evaluation receipt v1\x00" + json.dumps(payload, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        return {**payload, "signature": {"algorithm": "Ed25519", "key_id": self.key_id,
                    "value": base64.b64encode(self.key.sign(canonical)).decode()}}

    def run_one(self):
        if not self.ready:
            return False
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return False
            db.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (utcnow(), row["id"]))
        job, work = dict(row), self.uploads / row["id"]
        bundle, output = work / "submission.zip", work / "result.json"
        try:
            batch_hash = sha256(bundle)
            if self.runner:
                result = self.runner(bundle, work)
            else:
                env = {"PATH": os.defpath, "PYTHONPATH": str(Path(__file__).parent.parent),
                       "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                       "AUTORSE_PRIVATE_DIR": str(self.private_root), "PYTHONDONTWRITEBYTECODE": "1"}
                command = [sys.executable, "-m", "selfhost.engine", "--worker", str(self.runtime),
                           str(self.private_root), str(bundle), str(output), str(work)]
                process = subprocess.Popen(command, cwd=work, env=env, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True)
                try:
                    returncode = process.wait(timeout=1200)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise ValueError("Scoring time limit reached") from None
                if returncode != 0 or not output.is_file() or output.stat().st_size > 1024**2:
                    raise ValueError()
                result = json.loads(output.read_text())
            receipt = self.make_receipt(result, job, batch_hash)
            with self.db() as db:
                db.execute("UPDATE jobs SET status='complete',receipt=?,updated=? WHERE id=?",
                           (json.dumps(receipt, allow_nan=False), utcnow(), row["id"]))
        except Exception:
            self.fail(row["id"])
        finally:
            self.remove_upload(row["id"])
        return True

    def loop(self):
        while not self.stop_event.is_set():
            if not self.run_one():
                self.wake.wait(timeout=5)
                self.wake.clear()


if __name__ == "__main__":
    if len(sys.argv) == 7 and sys.argv[1] == "--worker":
        raise SystemExit(worker_main(sys.argv[2:]))
    raise SystemExit(2)
