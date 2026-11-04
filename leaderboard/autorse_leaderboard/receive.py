"""Restricted SSH publication receiver; never interpret a client command as shell.

Install the entry point and this package root-owned. The dedicated SSH account
may write only /var/lib/autorse/published; it must not modify the key registry or
the application. There are deliberately no command-line path options.
"""
from __future__ import annotations

import fcntl
import io
import json
import os
from pathlib import Path
import re
import signal
import shutil
import stat
import sys
import tempfile
import uuid
import zipfile

from .cli import read_json
from .snapshot import (MANIFEST_NAME, MAX_JSON_BYTES, MAX_SNAPSHOT_BYTES, MAX_SNAPSHOT_FILES,
                       _BASE_FILES, _SUBMISSION, _require, verify_snapshot)

PUBLISHED_ROOT = Path("/var/lib/autorse/published")
TRUSTED_KEYS_FILE = Path("/etc/autorse/trusted-keys.json")
_COMMAND = re.compile(r"publish ([0-9a-f]{64})\Z")


def command_digest(command):
    match = _COMMAND.fullmatch(command or "")
    _require(bool(match), "publication_command_refused")
    return match[1]


def unpack_snapshot(stream, directory):
    """Extract only bounded, regular allowlisted JSON members; no extractall."""
    data = stream.read(MAX_SNAPSHOT_BYTES + 1)
    _require(0 < len(data) <= MAX_SNAPSHOT_BYTES, "publication_archive_size_limit")
    root = Path(directory)
    root.mkdir(mode=0o700)
    names, total = set(), 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        _require(1 <= len(members) <= MAX_SNAPSHOT_FILES, "publication_file_count_limit")
        for member in members:
            name = member.filename
            allowed = name == MANIFEST_NAME or name in _BASE_FILES or bool(_SUBMISSION.fullmatch(name))
            _require(allowed and name not in names and not member.is_dir()
                     and (not name.startswith("submissions/") or len(Path(name).stem) <= 80),
                     "publication_archive_path_refused")
            file_type = stat.S_IFMT(member.external_attr >> 16)
            _require(file_type in (0, stat.S_IFREG) and not member.flag_bits & 1
                     and member.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                     "publication_archive_member_refused")
            _require(0 < member.file_size <= MAX_JSON_BYTES, "publication_file_size_limit")
            total += member.file_size
            _require(total <= MAX_SNAPSHOT_BYTES, "publication_expanded_size_limit")
            names.add(name)
        _require(MANIFEST_NAME in names and _BASE_FILES <= names, "publication_archive_incomplete")
        for member in members:
            path = root / member.filename
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with archive.open(member) as source, path.open("xb") as destination:
                remaining = member.file_size
                while remaining:
                    chunk = source.read(min(64 * 1024, remaining))
                    _require(bool(chunk), "publication_member_truncated")
                    destination.write(chunk)
                    remaining -= len(chunk)
                _require(not source.read(1), "publication_member_size_mismatch")
    return root


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install_snapshot(checked, root):
    """Install verified bytes as one release and atomically switch current."""
    root = Path(root)
    releases = root / "snapshots"
    _require(not root.is_symlink() and not releases.is_symlink(), "publication_root_symlink_refused")
    releases.mkdir(mode=0o755, exist_ok=True)
    digest = checked.audit["manifest_sha256"]
    release = releases / digest
    _require(not release.is_symlink(), "publication_release_symlink_refused")
    files = dict(checked.files)
    files["verification.json"] = (json.dumps(checked.audit, indent=2) + "\n").encode()
    if release.exists():
        actual = {path.relative_to(release).as_posix() for path in release.rglob("*") if path.is_file()}
        _require(actual == set(files) and not any(path.is_symlink() for path in release.rglob("*")),
                 "publication_release_conflict")
        _require(all((release / name).read_bytes() == data for name, data in files.items()),
                 "publication_release_conflict")
    else:
        staging = Path(tempfile.mkdtemp(prefix=".release-", dir=releases))
        try:
            for name, data in files.items():
                path = staging / name
                path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    os.fchmod(stream.fileno(), 0o644)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            os.chmod(staging, 0o755)
            for directory in sorted((p for p in staging.rglob("*") if p.is_dir()),
                                    key=lambda p: len(p.parts), reverse=True):
                _fsync_directory(directory)
            _fsync_directory(staging)
            os.rename(staging, release)
            _fsync_directory(releases)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    current = root / "current"
    _require(not current.exists() or current.is_symlink(), "publication_current_not_symlink")
    temporary = root / (".current-" + uuid.uuid4().hex)
    try:
        temporary.symlink_to(Path("snapshots") / digest, target_is_directory=True)
        os.replace(temporary, current)
        _fsync_directory(root)
    finally:
        if temporary.is_symlink():
            temporary.unlink()
    return checked.audit


def receive(command, stream, trusted_keys, root, *, artifact_reader=None):
    digest = command_digest(command)
    root = Path(root)
    _require(root.is_dir() and not root.is_symlink(), "publication_root_not_ready")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(root / ".publish.lock", flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(prefix=".incoming-", dir=root) as temporary:
            folder = unpack_snapshot(stream, Path(temporary) / "payload")
            checked = verify_snapshot(folder, trusted_keys, digest, artifact_reader=artifact_reader,
                                      _authenticated_publisher_evidence=artifact_reader is None)
            return install_snapshot(checked, root)
    finally:
        os.close(fd)


def main():
    def expired(_signal, _frame):
        raise TimeoutError("publication_deadline_exceeded")
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(180)
    try:
        _require(len(sys.argv) == 1, "publication_arguments_refused")
        command_digest(os.environ.get("SSH_ORIGINAL_COMMAND"))
        _require(TRUSTED_KEYS_FILE.is_file() and not TRUSTED_KEYS_FILE.is_symlink(),
                 "publication_key_registry_missing")
        for path in (TRUSTED_KEYS_FILE, TRUSTED_KEYS_FILE.parent):
            metadata = path.stat()
            _require(metadata.st_uid == 0 and not metadata.st_mode & 0o022,
                     "publication_key_registry_not_trusted")
        audit = receive(os.environ["SSH_ORIGINAL_COMMAND"], sys.stdin.buffer,
                        read_json(TRUSTED_KEYS_FILE), PUBLISHED_ROOT)
        print(json.dumps({"ok": True, "source_commit": audit["source_commit"],
                          "entry_count": audit["entry_count"], "snapshot_signed": False}))
        return 0
    except Exception:
        print(json.dumps({"ok": False, "error": "publication_refused"}))
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
