"""Verify a trusted publication hand-off before replacing a self-hosted board.

The SHA256 manifest is not a signature. Its expected digest must arrive through
the authenticated maintainer deployment channel, separately from public uploads.
Receipt signatures and the publication's review bindings are checked again; no
participant code or uploaded trajectory is executed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .cli import check_approval_bytes, read_json
from .ranking import build_leaderboard
from .validation import validate_submission

REPOSITORY = "Ray-Tiann/AutoRSE"
MANIFEST_NAME = "snapshot-manifest.json"
MAX_JSON_BYTES = 2 * 1024**2
MAX_SNAPSHOT_FILES = 256
MAX_SNAPSHOT_BYTES = 32 * 1024**2
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SUBMISSION = re.compile(r"submissions/([a-z0-9]+(?:-[a-z0-9]+)*)\.json\Z")
_BASE_FILES = {"community-leaderboard.json", "approval-ledger.json"}
_PUBLICATION_CHECKS = {"qualified_github_review": True, "pinned_evidence_integrity": True,
                       "signed_receipts": True, "benchmark_only": True}


@dataclass(frozen=True)
class VerifiedSnapshot:
    board: dict
    audit: dict
    files: dict[str, bytes]


def _require(value, message):
    if not value:
        raise ValueError(message)


def _json_bytes(data):
    _require(0 < len(data) <= MAX_JSON_BYTES, "invalid_or_oversized_snapshot_json")
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "snapshot_duplicate_json_key")
            result[key] = value
        return result
    def constant(_value):
        raise ValueError("snapshot_nonfinite_json")
    value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    _require(type(value) is dict, "snapshot_json_must_be_object")
    return value


def _source_file(root, name):
    _require(name in _BASE_FILES or bool(_SUBMISSION.fullmatch(name)), "invalid_snapshot_path")
    path = root / name
    _require(not any(part.is_symlink() for part in (path, *path.parents)
                     if part == root or root in part.parents), "snapshot_symlink_refused")
    _require(path.is_file() and 0 < path.stat().st_size <= MAX_JSON_BYTES,
             "invalid_or_oversized_snapshot_file")
    return path


def write_manifest(folder, submission_names, source_commit, *, empty_source_check=None):
    """Create a content manifest inside the already-reviewed CI output folder."""
    _require(type(source_commit) is str and bool(_HEX40.fullmatch(source_commit)),
             "invalid_snapshot_source_commit")
    root = Path(folder)
    names = _BASE_FILES | {"submissions/" + name for name in submission_names}
    _require(len(names) + 1 <= MAX_SNAPSHOT_FILES, "snapshot_file_count_limit")
    files = {}
    for name in sorted(names):
        data = _source_file(root, name).read_bytes()
        files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    count = len(names) - len(_BASE_FILES)
    _require(count > 0 or type(empty_source_check) is dict, "empty_snapshot_requires_source_tree_check")
    value = {"schema_version": 1, "source_repository": REPOSITORY,
             "source_commit": source_commit, "files": files,
             "publisher_workflow": ".github/workflows/publish-leaderboard.yml" if count else None,
             "publication_kind": "reviewed-submissions" if count else "empty-source-bootstrap",
             "publication_checks": dict(_PUBLICATION_CHECKS) if count else {},
             "submission_count": count}
    if not count:
        value["empty_source_check"] = empty_source_check
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    _require(len(data) + sum(ref["size"] for ref in files.values()) <= MAX_SNAPSHOT_BYTES,
             "snapshot_total_size_limit")
    (root / MANIFEST_NAME).write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def verify_snapshot(folder, trusted_keys, expected_manifest_sha256, *, artifact_reader=None,
                    _authenticated_publisher_evidence=False):
    """Recheck a pinned CI snapshot; do not infer approval from a fresh hash."""
    root = Path(folder)
    _require(root.is_dir() and not root.is_symlink(), "invalid_snapshot_directory")
    _require(type(expected_manifest_sha256) is str
             and bool(_HEX64.fullmatch(expected_manifest_sha256)), "expected_manifest_digest_required")
    manifest_path = root / MANIFEST_NAME
    _require(not manifest_path.is_symlink() and manifest_path.is_file()
             and 0 < manifest_path.stat().st_size <= MAX_JSON_BYTES, "invalid_snapshot_manifest")
    raw_manifest = manifest_path.read_bytes()
    _require(hashlib.sha256(raw_manifest).hexdigest() == expected_manifest_sha256,
             "snapshot_manifest_digest_mismatch")
    manifest = _json_bytes(raw_manifest)
    source = manifest.get("source_commit")
    files = manifest.get("files")
    _require(manifest.get("schema_version") == 1 and manifest.get("source_repository") == REPOSITORY
             and type(source) is str and bool(_HEX40.fullmatch(source)) and type(files) is dict,
             "invalid_snapshot_manifest")
    kind = manifest.get("publication_kind")
    _require(kind in ("reviewed-submissions", "empty-source-bootstrap"),
             "snapshot_publication_attestation_missing")
    if kind == "reviewed-submissions":
        checks = manifest.get("publication_checks")
        _require(manifest.get("publisher_workflow") == ".github/workflows/publish-leaderboard.yml"
                 and type(checks) is dict and set(checks) == set(_PUBLICATION_CHECKS)
                 and all(value is True for value in checks.values()),
                 "snapshot_publication_attestation_missing")
    else:
        source_check = manifest.get("empty_source_check")
        _require(manifest.get("publisher_workflow") is None
                 and manifest.get("publication_checks") == {} and manifest.get("submission_count") == 0
                 and type(source_check) is dict
                 and source_check.get("registry_path") == ".github/leaderboard-submissions"
                 and type(source_check.get("submission_json_count")) is int
                 and source_check["submission_json_count"] == 0
                 and type(source_check.get("git_tree_sha")) is str
                 and bool(_HEX40.fullmatch(source_check["git_tree_sha"])),
                 "invalid_empty_source_bootstrap")
    _require(_BASE_FILES <= set(files), "snapshot_base_files_missing")
    _require(len(files) + 1 <= MAX_SNAPSHOT_FILES, "snapshot_file_count_limit")
    checked_files = {MANIFEST_NAME: raw_manifest}
    total_bytes = len(raw_manifest)
    for name, reference in files.items():
        path = _source_file(root, name)
        _require(type(reference) is dict and set(reference) == {"sha256", "size"}
                 and type(reference["sha256"]) is str and bool(_HEX64.fullmatch(reference["sha256"]))
                 and type(reference["size"]) is int and reference["size"] == path.stat().st_size,
                 "invalid_snapshot_file_reference")
        data = path.read_bytes()
        _require(len(data) == reference["size"]
                 and hashlib.sha256(data).hexdigest() == reference["sha256"],
                 "snapshot_file_digest_mismatch")
        total_bytes += len(data)
        _require(total_bytes <= MAX_SNAPSHOT_BYTES, "snapshot_total_size_limit")
        checked_files[name] = data

    ledger = _json_bytes(checked_files["approval-ledger.json"])
    _require(ledger.get("schema_version") == 1 and ledger.get("repository") == REPOSITORY
             and ledger.get("main_sha") == source and type(ledger.get("approvals")) is list,
             "snapshot_review_source_mismatch")
    names = []
    for approval in ledger["approvals"]:
        _require(type(approval) is dict, "invalid_snapshot_approval")
        main_path = approval.get("submission_path")
        _require(type(main_path) is str and main_path.startswith(".github/leaderboard-submissions/"),
                 "invalid_snapshot_submission_path")
        name = "submissions/" + main_path.removeprefix(".github/leaderboard-submissions/")
        match = _SUBMISSION.fullmatch(name)
        _require(bool(match) and len(match[1]) <= 80 and name not in names,
                 "invalid_or_duplicate_snapshot_submission")
        names.append(name)
    _require(set(files) == _BASE_FILES | set(names), "snapshot_file_set_mismatch")
    _require(type(manifest.get("submission_count")) is int and manifest["submission_count"] == len(names),
             "snapshot_submission_count_mismatch")
    _require(bool(names) if kind == "reviewed-submissions" else not names,
             "snapshot_publication_kind_mismatch")

    if artifact_reader is None and names and not _authenticated_publisher_evidence:
        from .artifacts import PublicArtifactReader
        artifact_reader = PublicArtifactReader()
    summaries = []
    for name in names:
        submission = _json_bytes(checked_files[name])
        _require(submission.get("id") == Path(name).stem and submission.get("kind") == "benchmark",
                 "snapshot_submission_not_benchmark")
        check_approval_bytes(checked_files[name], submission, ledger)
        report = validate_submission(submission, trusted_keys, artifact_reader=artifact_reader)
        if _authenticated_publisher_evidence:
            # Only the root-owned forced-command receiver enables this branch.
            # The authenticated CI publisher already checked every public file;
            # metadata-only validation still must pass every receipt/protocol/run
            # check. This does not turn an ordinary metadata report publishable.
            failures = {item["code"] for item in report["checks"] if not item["passed"]}
            _require(report.get("metadata_valid") is True
                     and failures <= {"artifacts.pending"} and bool(report.get("summary")),
                     "snapshot_submission_validation_failed")
        else:
            _require(report.get("valid") is True and report.get("publishable") is True,
                     "snapshot_submission_validation_failed")
        summary = report["summary"]
        if _authenticated_publisher_evidence:
            summary["publishable"] = True
        summary["source_url"] = (f"https://github.com/{REPOSITORY}/blob/{source}/"
                                 f".github/leaderboard-submissions/{submission['id']}.json")
        summaries.append(summary)
    expected = build_leaderboard(summaries)
    expected["metadata"].update(source_repository=REPOSITORY, source_commit=source)
    board = _json_bytes(checked_files["community-leaderboard.json"])
    _require(board == expected, "published_board_differs_from_verified_submissions")
    audit = {"schema_version": 1, "source_repository": REPOSITORY, "source_commit": source,
             "manifest_sha256": expected_manifest_sha256,
             "board_sha256": files["community-leaderboard.json"]["sha256"],
             "entry_count": len(summaries), "receipt_signatures_verified": len(summaries) * 3,
             "snapshot_signed": False,
             "trust_source": "Expected manifest SHA256 supplied through authenticated maintainer deployment.",
             "review_binding": "Matched the pinned publication ledger; live GitHub permissions were not re-queried.",
             "evidence_verification": ("Attested by authenticated CI publisher; receiver did not independently fetch evidence."
                                       if _authenticated_publisher_evidence else
                                       "Pinned evidence bytes fetched and checked by this verifier.")}
    if not names:
        audit.update(review_binding="No submission JSON exists in the recorded source tree; no human reviews are asserted.",
                     evidence_verification="Not applicable: empty initial community cohort.")
    return VerifiedSnapshot(board=board, audit=audit, files=checked_files)


def _atomic_write(path, data):
    path = Path(path)
    _require(not path.is_symlink(), "snapshot_output_symlink_refused")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--keys", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        checked = verify_snapshot(args.snapshot_dir, read_json(args.keys), args.expected_manifest_sha256)
        # Preserve the exact checked bytes, not a reformatted JSON representation.
        _atomic_write(args.output_file, checked.files["community-leaderboard.json"])
        if args.report:
            _atomic_write(args.report, (json.dumps(checked.audit, indent=2) + "\n").encode())
        print(json.dumps({"ok": True, "entry_count": len(checked.board["rows"]),
                          "source_commit": checked.audit["source_commit"], "snapshot_signed": False}))
        return 0
    except Exception:
        # Do not log evidence content, URLs carrying credentials, or local key paths.
        print(json.dumps({"ok": False, "error": "snapshot_verification_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
