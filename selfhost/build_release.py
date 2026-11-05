#!/usr/bin/env python3
"""Build an allowlisted, source-only AutoRSE server release; never package secrets."""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
TASKS = ("hstu", "intsr", "tiger", "onetrans", "rankmixer", "wukong")
PUBLIC_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".png", ".pdf", ".csv", ".txt", ".ico", ".webp"}
MAX_FILE_BYTES = 5 * 1024**2
MAX_RELEASE_BYTES = 32 * 1024**2
PAPER_ORIGIN = "https://ray-tiann.github.io/AutoRSE_WEB"
HF_EVALUATOR = "https://huggingface.co/spaces/Ray0311/AutoRSE-Evaluator"
HF_RESEARCH_CHANGES = "https://ray0311-autorse-leaderboard.static.hf.space/changes.html"
ZIP_PARSER_SHA = "81bbbde785820a072414202bd05196e20eae0b6ce2717a85420a5ce141f7f7f4"
INSIGHT_ASSETS = ("insights.js", "insights.css", "insights-data.json", "paper-run-resources.csv", "changes.html")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.port not in (None, 443)):
        raise ValueError("Public origin must be one HTTPS origin, with no credentials/path/query")
    host = parsed.hostname
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("Public origin must use a public IP address or DNS hostname")
    except ValueError as error:
        if re.fullmatch(r"[0-9.]+", host) or ":" in host:
            raise ValueError("Public origin IP is not globally routable") from error
        if host == "localhost" or not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "." not in host:
            raise ValueError("Invalid public hostname") from error
    return value.rstrip("/")


def checked_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"Source is missing, a symlink, or over the size allowlist: {path}")
    data = path.read_bytes()
    if b"-----BEGIN " in data and b"PRIVATE KEY-----" in data:
        raise ValueError(f"Private key material must never enter the source release: {path}")
    if re.search(rb"\bhf_[A-Za-z0-9]{28,}\b", data):
        raise ValueError(f"Possible Hugging Face credential in source release: {path}")
    return data


def put(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o644)


def copy(source: Path, destination: Path) -> None:
    put(destination, checked_bytes(source))


def tree(source: Path, destination: Path, *, suffixes: set[str]) -> None:
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"Missing source directory or unexpected symlink: {source}")
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not accepted in source assets: {path}")
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.name.startswith("."):
            continue
        if path.suffix not in suffixes:
            raise ValueError(f"Unexpected source asset type: {path}")
        copy(path, destination / path.relative_to(source))


def revision(root: Path) -> str | None:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def build(output: Path, *, origin: str, source: Path = ROOT) -> dict:
    origin = public_origin(origin)
    source = source.resolve()
    if output.exists():
        raise ValueError("Output already exists; choose a new versioned release directory")
    if output.resolve().is_relative_to(source):
        raise ValueError("Build outputs must be outside the source checkout")
    output.mkdir(parents=True)
    try:
        # Public web root: a strict set of site assets, never runtime code or inputs.
        tree(source / "assets", output / "public/assets", suffixes=PUBLIC_SUFFIXES)
        for name in ("index.html", "robots.txt", "sitemap.xml"):
            if (source / name).is_file():
                text = checked_bytes(source / name).decode("utf-8")
                text = text.replace(PAPER_ORIGIN, origin).replace(HF_EVALUATOR, origin + "/evaluate/")
                text = text.replace(HF_RESEARCH_CHANGES, origin + "/leaderboard/changes.html")
                put(output / "public" / name, text.encode())
        local_embed = checked_bytes(source / "selfhost/templates/leaderboard-local.js")
        put(output / "public/assets/js/leaderboard.js", local_embed)
        config = {"spaceUrl": origin + "/leaderboard/", "embedUrl": origin + "/leaderboard/?embed=1"}
        put(output / "public/assets/data/leaderboard.json", (json.dumps(config, indent=2) + "\n").encode())
        board = checked_bytes(source / "hf-leaderboard/index.html").decode()
        old_target = ",'https://ray-tiann.github.io'))"
        if old_target not in board:
            raise ValueError("Unrecognized leaderboard postMessage boundary; review embed before releasing")
        board = board.replace(old_target, ",window.location.origin))")
        board = board.replace(HF_EVALUATOR, origin + "/evaluate/")
        put(output / "public/leaderboard/index.html", board.encode())
        seed = re.search(r'<script type="application/json" id="seed-data">(.*?)</script>', board, re.S)
        if not seed or not isinstance(json.loads(seed.group(1)), dict):
            raise ValueError("Missing paper reference seed; do not manufacture a replacement")
        put(output / "public/leaderboard/leaderboard-data.json", (seed.group(1) + "\n").encode())
        # Only the five reviewed insight assets belong beside the leaderboard.
        # Never glob this maintenance directory: it can contain deployment notes
        # or incoming snapshots that are not application assets.
        for name in INSIGHT_ASSETS:
            copy(source / "hf-leaderboard" / name, output / "public/leaderboard" / name)
        # Runtime: public submission contracts plus the exact fixed CPU scorers.
        for name in ("__init__.py", "release.py", "tasks.py", "submissions.py"):
            copy(source / "autorse" / name, output / "runtime/autorse" / name)
        copy(source / "space/service.py", output / "runtime/space/service.py")
        for task in TASKS:
            copy(source / "space/scorers" / f"{task}.py", output / "runtime/space/scorers" / f"{task}.py")
        parser = checked_bytes(source / "selfhost/runtime_sources/batch_submission.py")
        if sha(parser) != ZIP_PARSER_SHA:
            raise ValueError("The reviewed ZIP parser changed; update provenance only after review")
        put(output / "runtime/space/batch_submission.py", parser)
        copy(source / "leaderboard/autorse_leaderboard/receipts.py", output / "runtime/space/receipt_signing.py")
        copy(source / "selfhost/runtime_sources/PROVENANCE.json", output / "runtime/ZIP_PARSER_PROVENANCE.json")
        # App and infrastructure have their own non-public directory.
        for name in ("app.py", "auth.py", "engine.py", "admin.py"):
            copy(source / "selfhost" / name, output / "selfhost" / name)
        put(output / "selfhost/__init__.py", b'"""AutoRSE self-hosted service."""\n')
        tree(source / "selfhost/static", output / "selfhost/static", suffixes={".css", ".js", ".html", ".svg"})
        copy(source / "selfhost/requirements.txt", output / "requirements.txt")
        tree(source / "selfhost/deploy", output / "deploy", suffixes={".service", ".template", ".example", ".timer", ".sh"})
        copy(source / "leaderboard/receive_snapshot.py", output / "publisher/receive_snapshot.py")
        tree(source / "leaderboard/autorse_leaderboard", output / "publisher/autorse_leaderboard", suffixes={".py"})
        copy(source / "leaderboard/trusted-keys.json", output / "publisher/trusted-keys.json")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            copy(source / name, output / name)
        for path in output.rglob("*.py"):
            ast.parse(path.read_text(), filename=str(path.relative_to(output)))
        files = [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size,
                  "sha256": sha(path.read_bytes())}
                 for path in sorted(output.rglob("*")) if path.is_file()]
        if sum(row["bytes"] for row in files) > MAX_RELEASE_BYTES:
            raise ValueError("Source release exceeds the overall size allowlist")
        manifest = {"schema_version": 1, "format": "autorse-selfhost-source-v1", "public_origin": origin,
                    "source_repository": "https://github.com/Ray-Tiann/AutoRSE_WEB",
                    "source_commit": revision(source), "backend": "numpy-cpu-v1",
                    "private_data_included": False, "secret_keys_included": False,
                    "public_snapshot_included": False,
                    "snapshot_path": "/var/lib/autorse/published/current",
                    "files": files}
        put(output / "MANIFEST.json", (json.dumps(manifest, indent=2) + "\n").encode())
        sums = "".join(f"{sha(path.read_bytes())}  {path.relative_to(output).as_posix()}\n"
                       for path in sorted(output.rglob("*")) if path.is_file())
        put(output / "SHA256SUMS", sums.encode())
        verify(output)
        return manifest
    except Exception:
        # This is a newly created, task-owned build directory only.
        shutil.rmtree(output)
        raise


def verify(directory: Path) -> dict:
    directory = directory.resolve()
    data = json.loads((directory / "MANIFEST.json").read_text())
    if (data.get("format") != "autorse-selfhost-source-v1"
            or data.get("private_data_included") is not False
            or data.get("secret_keys_included") is not False):
        raise ValueError("Unrecognized or unsafe release manifest")
    public_origin(data["public_origin"])
    paths = [row["path"] for row in data["files"]]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate manifest paths")
    listed = set(paths) | {"MANIFEST.json", "SHA256SUMS"}
    actual = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Release contains symlinks")
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if listed != actual:
        raise ValueError("Release inventory does not exactly match its manifest")
    for row in data["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid manifest path")
        blob = checked_bytes(directory / relative)
        if len(blob) != row["bytes"] or sha(blob) != row["sha256"]:
            raise ValueError(f"Release hash/size mismatch: {relative}")
    expected_sums = "".join(f"{sha(path.read_bytes())}  {path.relative_to(directory).as_posix()}\n"
                            for path in sorted(directory.rglob("*"))
                            if path.is_file() and path.name != "SHA256SUMS")
    if (directory / "SHA256SUMS").read_text() != expected_sums:
        raise ValueError("Release SHA256SUMS does not match all payload files and its manifest")
    return data


def archive(directory: Path, destination: Path) -> str:
    verify(directory)
    if destination.exists():
        raise ValueError("Archive already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Fixed archive metadata makes the compressed transport reproducible.
    with destination.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as tar:
            for path in sorted(directory.rglob("*")):
                if not path.is_file():
                    continue
                blob = path.read_bytes()
                info = tarfile.TarInfo(path.relative_to(directory).as_posix())
                info.size, info.mode, info.mtime, info.uid, info.gid = len(blob), 0o644, 0, 0, 0
                tar.addfile(info, io.BytesIO(blob))
    return sha(destination.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--origin")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        data = verify(args.verify)
        print(json.dumps({"verified": True, "files": len(data["files"]), "origin": data["public_origin"]}))
        return
    if not args.output or not args.origin:
        parser.error("--output and --origin are required when building")
    data = build(args.output, origin=args.origin, source=args.source_root)
    result = {"release": str(args.output), "files": len(data["files"]),
              "bytes": sum(row["bytes"] for row in data["files"]), "origin": data["public_origin"]}
    if args.archive:
        result.update(archive=str(args.archive), archive_sha256=archive(args.output, args.archive))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
