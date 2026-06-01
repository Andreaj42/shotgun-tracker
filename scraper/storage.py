import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path("data/shotgun.sqlite")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                organizer TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)

        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(events)").fetchall()
        }

        if "is_active" not in columns:
            conn.execute(
                "ALTER TABLE events ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(event_id, name),
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS availability_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_type_id INTEGER NOT NULL,
                scraped_at TEXT NOT NULL,
                available_count INTEGER,
                ok INTEGER NOT NULL,
                error TEXT,
                warning TEXT,
                FOREIGN KEY(ticket_type_id) REFERENCES ticket_types(id)
            )
        """)


def mark_all_events_inactive():
    with get_connection() as conn:
        conn.execute("UPDATE events SET is_active = 0")


def upsert_event(conn, event_url: str, organizer: str | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn.execute(
        """
        INSERT INTO events(url, organizer, created_at, last_seen_at, is_active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(url) DO UPDATE SET
            organizer = excluded.organizer,
            last_seen_at = excluded.last_seen_at,
            is_active = 1
        """,
        (event_url, organizer, now, now),
    )

    row = conn.execute(
        "SELECT id FROM events WHERE url = ?",
        (event_url,),
    ).fetchone()

    return row[0]


def mark_event_active(event_url: str, organizer: str | None = None) -> int:
    with get_connection() as conn:
        return upsert_event(conn, event_url, organizer)


def upsert_ticket_type(conn, event_id: int, ticket_name: str) -> int:
    conn.execute(
        """
        INSERT OR IGNORE INTO ticket_types(event_id, name)
        VALUES (?, ?)
        """,
        (event_id, ticket_name),
    )

    row = conn.execute(
        """
        SELECT id FROM ticket_types
        WHERE event_id = ? AND name = ?
        """,
        (event_id, ticket_name),
    ).fetchone()

    return row[0]


def save_ticket_snapshot(result: dict):
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with get_connection() as conn:
        event_id = upsert_event(
            conn,
            result["event_url"],
            result.get("organizer"),
        )
        ticket_name = result["ticket_name"] or "__unknown__"
        ticket_type_id = upsert_ticket_type(conn, event_id, ticket_name)

        conn.execute(
            """
            INSERT INTO availability_snapshots(
                ticket_type_id,
                scraped_at,
                available_count,
                ok,
                error,
                warning
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_type_id,
                scraped_at,
                result["available_count"],
                int(result["ok"]),
                result["error"],
                result.get("warning"),
            ),
        )
