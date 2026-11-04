"""Local SSH-only queue inspection. No HTTP administrator interface is exposed."""
import argparse
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path("/var/lib/autorse/state"))
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    database = args.state_dir.resolve() / "autorse.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id,display_name,participant_kind,status,created,updated,error FROM jobs ORDER BY created DESC LIMIT ?",
                          (args.limit,)).fetchall()
    print(json.dumps([dict(row) for row in rows], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
