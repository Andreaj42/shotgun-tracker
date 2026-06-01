import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scraper.discovery import discover_all_events


async def main():
    events = await discover_all_events()

    for event in events:
        print(event)


if __name__ == "__main__":
    asyncio.run(main())
