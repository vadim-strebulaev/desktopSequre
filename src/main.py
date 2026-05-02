from __future__ import annotations

from pathlib import Path

from .ui import run_app


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    db_path = base / "guard_terminal.sqlite3"
    return run_app(db_path)


if __name__ == "__main__":
    raise SystemExit(main())

