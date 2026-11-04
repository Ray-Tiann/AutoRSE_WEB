"""Package only a publisher snapshot's hash-checked JSON files for SSH delivery."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

from .cli import read_json
from .snapshot import (MANIFEST_NAME, MAX_JSON_BYTES, MAX_SNAPSHOT_BYTES, MAX_SNAPSHOT_FILES,
                       _source_file, _require)


def package(folder, output):
    root, output = Path(folder), Path(output)
    path = root / MANIFEST_NAME
    _require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_JSON_BYTES,
             "snapshot_manifest_missing")
    manifest_bytes = path.read_bytes()
    manifest = read_json(path)
    references = manifest.get("files")
    _require(type(references) is dict and len(references) + 1 <= MAX_SNAPSHOT_FILES,
             "snapshot_file_count_limit")
    files = {MANIFEST_NAME: manifest_bytes}
    total = len(manifest_bytes)
    for name, reference in references.items():
        data = _source_file(root, name).read_bytes()
        _require(type(reference) is dict and reference.get("size") == len(data)
                 and reference.get("sha256") == hashlib.sha256(data).hexdigest(),
                 "snapshot_packaging_digest_mismatch")
        files[name] = data
        total += len(data)
        _require(total <= MAX_SNAPSHOT_BYTES, "snapshot_total_size_limit")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    archive = buffer.getvalue()
    _require(len(archive) <= MAX_SNAPSHOT_BYTES, "snapshot_archive_size_limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(archive)
        stream.flush()
        os.fsync(stream.fileno())
    return {"manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "archive_size": len(archive), "file_count": len(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps({"ok": True, **package(args.snapshot_dir, args.output)}))
        return 0
    except Exception:
        print(json.dumps({"ok": False, "error": "snapshot_packaging_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
