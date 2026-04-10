"""Module entrypoint for the operator CLI."""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    if __package__ in (None, ""):
        repo_root = Path(__file__).resolve().parent.parent
        repo_root_str = str(repo_root)
        if repo_root_str not in sys.path:
            sys.path.insert(0, repo_root_str)

    from admin.cli import main

    raise SystemExit(main())
