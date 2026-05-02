from __future__ import annotations

from pathlib import Path

# Support running as a module (`python -m src.main`) and as a script
# (`python src/main.py`). The relative import only works in module mode.
try:
    from .ui import run_app
except ImportError:  # pragma: no cover
    from ui import run_app


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    db_path = base / "guard_terminal.sqlite3"
    return run_app(db_path)


if __name__ == "__main__":
    raise SystemExit(main())
