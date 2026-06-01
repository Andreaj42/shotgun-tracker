import asyncio
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scraper.discovery import discover_all_events
from scraper.storage import (
    init_db,
    mark_all_events_inactive,
    mark_event_active,
    save_ticket_snapshot,
)
from scraper.shotgun import scrape_event_tickets


async def main():
    debug = os.getenv("SHOTGUN_DEBUG", "").lower() in ("1", "true", "yes", "on")

    init_db()
    events = await discover_all_events()
    mark_all_events_inactive()

    print("\nEvents discovered:")
    for event in events:
        mark_event_active(event["event_url"], event["organizer"])
        print(f"- {event['organizer']} | {event['event_url']}")

    print("\nScraping tickets...")

    for event in events:
        event_url = event["event_url"]
        organizer = event["organizer"]

        print(f"\nScraping: {event_url}")

        try:
            results = await scrape_event_tickets(event_url, debug=debug)

        except Exception as e:
            print(f"Erreur scraping événement {event_url}: {repr(e)}")
            continue

        for result in results:
            result["organizer"] = organizer
            save_ticket_snapshot(result)

            print(
                f"{organizer} | "
                f"{result['ticket_name']} | "
                f"available={result['available_count']} | "
                f"ok={result['ok']} | "
                f"error={result['error']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
