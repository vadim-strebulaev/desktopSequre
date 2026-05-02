from __future__ import annotations

from pathlib import Path

# Allow running the file either as a package (python -m src.main) where
# relative imports work, or directly (python src\main.py) where relative
# imports fail with "attempted relative import with no known parent package".
try:
    # Preferred when running as a package
    from .ui import run_app
except Exception:
    # Fallback for running the module as a script. Ensure the project root
    # (the directory that contains the `src` package) is on sys.path, then
    # import `src.ui` so its relative imports (e.g. `from .db import ...`)
    # resolve correctly.
    import sys
    import importlib

    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    run_app = importlib.import_module("src.ui").run_app


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    db_path = base / "guard_terminal.sqlite3"
    return run_app(db_path)


if __name__ == "__main__":
    raise SystemExit(main())

