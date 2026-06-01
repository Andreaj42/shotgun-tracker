import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/shotgun.sqlite")
OUTPUT_PATH = Path("docs/data/history.json")


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT
                e.url AS event_url,
                e.organizer,
                t.name AS ticket_name,
                s.scraped_at,
                s.available_count,
                s.ok,
                s.error,
                s.warning
            FROM availability_snapshots s
            JOIN ticket_types t ON t.id = s.ticket_type_id
            JOIN events e ON e.id = t.event_id
            WHERE e.is_active = 1
            ORDER BY e.url, t.name, s.scraped_at
        """).fetchall()

    data = {
        "events": {}
    }

    for row in rows:
        event_url = row["event_url"]
        ticket_name = row["ticket_name"]

        event = data["events"].setdefault(event_url, {
            "url": event_url,
            "organizer": row["organizer"],
            "tickets": {}
        })

        ticket = event["tickets"].setdefault(ticket_name, [])

        ticket.append({
            "timestamp": row["scraped_at"],
            "available_count": row["available_count"],
            "ok": bool(row["ok"]),
            "error": row["error"],
            "warning": row["warning"],
        })

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Export écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
