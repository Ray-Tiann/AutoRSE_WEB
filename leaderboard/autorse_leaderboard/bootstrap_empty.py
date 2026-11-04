"""Create an empty community snapshot only from an actually empty Git registry."""
import argparse
import json
from pathlib import Path
import re
import subprocess

from .cli import write_json
from .ranking import build_leaderboard
from .snapshot import REPOSITORY, _require, write_manifest

REGISTRY = ".github/leaderboard-submissions"


def _git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL,
                                   timeout=15, text=True).strip()


def bootstrap(checkout, source_commit, output):
    _require(type(source_commit) is str and bool(re.fullmatch(r"[0-9a-f]{40}", source_commit)),
             "bootstrap_commit_required")
    root, output = Path(checkout), Path(output)
    remote = _git(root, "remote", "get-url", "origin")
    _require(remote in ("https://github.com/Ray-Tiann/AutoRSE", "https://github.com/Ray-Tiann/AutoRSE.git",
                         "git@github.com:Ray-Tiann/AutoRSE.git"), "bootstrap_repository_mismatch")
    _require(_git(root, "rev-parse", "refs/remotes/origin/main") == source_commit,
             "bootstrap_requires_fetched_main_snapshot")
    entries = _git(root, "ls-tree", "-r", "--name-only", source_commit, "--", REGISTRY).splitlines()
    _require(bool(entries) and not any(name.endswith(".json") for name in entries),
             "bootstrap_requires_empty_submission_registry")
    tree = _git(root, "rev-parse", source_commit + "^{tree}")
    _require(bool(re.fullmatch(r"[0-9a-f]{40}", tree)), "bootstrap_tree_missing")
    _require(not output.exists() and not output.is_symlink(), "bootstrap_output_already_exists")
    output.mkdir(parents=True)
    ledger = {"schema_version": 1, "repository": REPOSITORY, "main_sha": source_commit, "approvals": []}
    board = build_leaderboard([])
    board["metadata"].update(source_repository=REPOSITORY, source_commit=source_commit)
    write_json(output / "approval-ledger.json", ledger)
    write_json(output / "community-leaderboard.json", board)
    digest = write_manifest(output, [], source_commit, empty_source_check={
        "registry_path": REGISTRY, "submission_json_count": 0, "git_tree_sha": tree})
    return {"source_commit": source_commit, "manifest_sha256": digest,
            "entry_count": 0, "reviews_asserted": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps({"ok": True, **bootstrap(args.source_checkout, args.source_commit, args.output_dir)}))
        return 0
    except Exception:
        print(json.dumps({"ok": False, "error": "empty_source_bootstrap_refused"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
