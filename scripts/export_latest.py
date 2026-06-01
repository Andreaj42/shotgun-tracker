import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/shotgun.sqlite")
OUTPUT_PATH = Path("docs/data/latest.json")


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT
                e.url AS event_url,
                e.organizer,
                t.name AS ticket_name,
                s.available_count,
                s.ok,
                s.error,
                s.warning,
                s.scraped_at
            FROM availability_snapshots s
            JOIN ticket_types t ON t.id = s.ticket_type_id
            JOIN events e ON e.id = t.event_id
            WHERE e.is_active = 1
              AND s.id IN (
                SELECT MAX(id)
                FROM availability_snapshots
                GROUP BY ticket_type_id
            )
            ORDER BY e.url, t.name
        """).fetchall()

    data = {
        "events": {}
    }

    for row in rows:
        event_url = row["event_url"]

        if event_url not in data["events"]:
            data["events"][event_url] = {
                "url": event_url,
                "organizer": row["organizer"],
                "tickets": []
            }

        data["events"][event_url]["tickets"].append({
            "name": row["ticket_name"],
            "available_count": row["available_count"],
            "ok": bool(row["ok"]),
            "error": row["error"],
            "warning": row["warning"],
            "scraped_at": row["scraped_at"],
        })

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Export écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
