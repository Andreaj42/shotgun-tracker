from playwright.async_api import async_playwright


ORGANIZER_URLS = {
    "encore": "https://shotgun.live/fr/venues/encore",
    "23-59": "https://shotgun.live/fr/venues/23-59",
}


async def discover_event_urls_from_organizer(organizer_name: str, organizer_url: str) -> list[dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            locale="fr-FR",
            viewport={"width": 1400, "height": 1600},
        )

        page = await context.new_page()
        await page.goto(organizer_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # Scroll pour forcer le chargement éventuel des cartes
        for _ in range(5):
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(1000)

        event_urls = await page.evaluate(
            """
            () => {
              const hasPastEventAncestor = element => {
                let current = element;

                while (current && current !== document.body) {
                  if (current.classList?.contains("opacity-60")) {
                    return true;
                  }

                  current = current.parentElement;
                }

                return false;
              };

              const links = [...document.querySelectorAll("a[href]")];

              return [...new Set(
                links
                  .filter(link => !hasPastEventAncestor(link))
                  .map(a => a.href)
                  .filter(href => href.includes("/events/"))
                  .map(href => href.split("?")[0])
              )];
            }
            """
        )

        await browser.close()

    return [
        {
            "organizer": organizer_name,
            "event_url": url,
        }
        for url in event_urls
    ]


async def discover_all_events() -> list[dict]:
    all_events = []

    for organizer_name, organizer_url in ORGANIZER_URLS.items():
        print(f"Discovery organizer: {organizer_name} | {organizer_url}")

        events = await discover_event_urls_from_organizer(
            organizer_name=organizer_name,
            organizer_url=organizer_url,
        )

        print(f"  -> {len(events)} event(s) found")

        all_events.extend(events)

    # déduplication : un événement peut être listé chez Encore et 23:59
    deduped = {}

    for event in all_events:
        event_url = event["event_url"]

        if event_url not in deduped:
            deduped[event_url] = event
        else:
            previous = deduped[event_url]["organizer"]
            current = event["organizer"]
            deduped[event_url]["organizer"] = f"{previous},{current}"

    return list(deduped.values())
