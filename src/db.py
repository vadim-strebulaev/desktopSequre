from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat(sep=" ")


@dataclass(frozen=True)
class Capacities:
    employee_parking: int
    guest_parking: int


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS employee_cards (
                card_number TEXT PRIMARY KEY,
                first_name   TEXT NOT NULL,
                last_name    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS visits (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number  TEXT NOT NULL,
                person_type  TEXT NOT NULL CHECK(person_type IN ('employee', 'guest')),
                first_name   TEXT NOT NULL,
                last_name    TEXT NOT NULL,
                entered_at   TEXT NOT NULL,
                exited_at    TEXT,
                guest_valid_hours INTEGER,
                FOREIGN KEY(card_number) REFERENCES employee_cards(card_number)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_visits_open
                ON visits(person_type, card_number, exited_at);

            CREATE TABLE IF NOT EXISTS parking_tickets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                person_type  TEXT NOT NULL CHECK(person_type IN ('employee', 'guest')),
                card_number  TEXT,
                car_plate    TEXT NOT NULL,
                issued_at    TEXT NOT NULL,
                closed_at    TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_parking_open
                ON parking_tickets(person_type, closed_at);

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        cur.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            ("employee_parking", "10"),
        )
        cur.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            ("guest_parking", "5"),
        )
        self.conn.commit()

    def get_capacities(self) -> Capacities:
        cur = self.conn.cursor()
        employee = int(cur.execute("SELECT value FROM settings WHERE key='employee_parking'").fetchone()[0])
        guest = int(cur.execute("SELECT value FROM settings WHERE key='guest_parking'").fetchone()[0])
        return Capacities(employee_parking=employee, guest_parking=guest)

    def set_capacities(self, capacities: Capacities) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO settings(key, value) VALUES('employee_parking', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(capacities.employee_parking),),
        )
        cur.execute(
            "INSERT INTO settings(key, value) VALUES('guest_parking', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(capacities.guest_parking),),
        )
        self.conn.commit()

    def upsert_employee_card(self, card_number: str, first_name: str, last_name: str) -> None:
        self.conn.execute(
            "INSERT INTO employee_cards(card_number, first_name, last_name) VALUES(?, ?, ?) "
            "ON CONFLICT(card_number) DO UPDATE SET first_name=excluded.first_name, last_name=excluded.last_name",
            (card_number, first_name, last_name),
        )
        self.conn.commit()

    def get_open_visit(self, person_type: str, card_number: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM visits WHERE person_type=? AND card_number=? AND exited_at IS NULL ORDER BY id DESC LIMIT 1",
            (person_type, card_number),
        ).fetchone()

    def open_employee_visit(self, card_number: str, first_name: str, last_name: str) -> None:
        self.upsert_employee_card(card_number, first_name, last_name)
        self.conn.execute(
            "INSERT INTO visits(card_number, person_type, first_name, last_name, entered_at) VALUES(?, 'employee', ?, ?, ?)",
            (card_number, first_name, last_name, _utc_now_iso()),
        )
        self.conn.commit()

    def close_employee_visit(self, card_number: str) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE visits SET exited_at=? WHERE id=(SELECT id FROM visits WHERE person_type='employee' AND card_number=? AND exited_at IS NULL ORDER BY id DESC LIMIT 1)",
            (_utc_now_iso(), card_number),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def open_guest_visit(self, pass_id: str, first_name: str, last_name: str, valid_hours: int) -> None:
        self.conn.execute(
            "INSERT INTO visits(card_number, person_type, first_name, last_name, entered_at, guest_valid_hours) "
            "VALUES(?, 'guest', ?, ?, ?, ?)",
            (pass_id, first_name, last_name, _utc_now_iso(), valid_hours),
        )
        self.conn.commit()

    def close_guest_visit(self, pass_id: str) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE visits SET exited_at=? WHERE id=(SELECT id FROM visits WHERE person_type='guest' AND card_number=? AND exited_at IS NULL ORDER BY id DESC LIMIT 1)",
            (_utc_now_iso(), pass_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_open_guest_overstays(self) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT * FROM visits WHERE person_type='guest' AND exited_at IS NULL AND guest_valid_hours IS NOT NULL"
        ).fetchall()

        overstays: list[sqlite3.Row] = []
        for row in rows:
            entered_at = datetime.fromisoformat(row["entered_at"])
            deadline = entered_at + timedelta(hours=int(row["guest_valid_hours"]))
            if datetime.utcnow() > deadline:
                overstays.append(row)
        return overstays

    def issue_parking_ticket(self, person_type: str, card_number: Optional[str], car_plate: str) -> None:
        self.conn.execute(
            "INSERT INTO parking_tickets(person_type, card_number, car_plate, issued_at) VALUES(?, ?, ?, ?)",
            (person_type, card_number, car_plate, _utc_now_iso()),
        )
        self.conn.commit()

    def close_parking_ticket(self, ticket_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE parking_tickets SET closed_at=? WHERE id=? AND closed_at IS NULL",
            (_utc_now_iso(), ticket_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def parking_open_counts(self) -> dict[str, int]:
        cur = self.conn.cursor()
        employee = cur.execute(
            "SELECT COUNT(*) FROM parking_tickets WHERE person_type='employee' AND closed_at IS NULL"
        ).fetchone()[0]
        guest = cur.execute(
            "SELECT COUNT(*) FROM parking_tickets WHERE person_type='guest' AND closed_at IS NULL"
        ).fetchone()[0]
        return {"employee": int(employee), "guest": int(guest)}

    def list_open_parking(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM parking_tickets WHERE closed_at IS NULL ORDER BY id DESC"
        ).fetchall()

