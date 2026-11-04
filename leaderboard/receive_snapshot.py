"""Root-owned SSH forced-command entry point. Run with Python's -I option."""
from pathlib import Path
import sys

# Only this deployed, root-owned package directory is added to isolated Python.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from autorse_leaderboard.receive import main

if __name__ == "__main__":
    raise SystemExit(main())
