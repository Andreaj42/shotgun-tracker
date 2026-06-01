import asyncio
import os

from playwright.async_api import async_playwright


DEFAULT_MAX_CLICKS = 2000
DEFAULT_TICKET_TIMEOUT_SECONDS = 300


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)

    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


JS_COUNT_SCRIPT = """
async ({ ticketName, delayMs, maxClicks, debug, progressEvery, ticketTimeoutMs }) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const norm = s => (s || "").toLowerCase().replace(/\\s+/g, " ").trim();
  const startedAt = Date.now();
  const isDisabled = button => {
    if (!button) return true;

    const className = String(button.className || "");
    const classList = className.split(/\\s+/);
    const style = window.getComputedStyle(button);

    return (
      button.disabled ||
      button.getAttribute("aria-disabled") === "true" ||
      className.includes("opacity-20") ||
      classList.includes("pointer-events-none") ||
      style.pointerEvents === "none"
    );
  };

  const title = [...document.querySelectorAll("h3")]
    .find(h => norm(h.innerText) === norm(ticketName));

  if (!title) {
    return { ok: false, error: "Titre du billet introuvable", added: null };
  }

  const ticketBlock = title.closest("[data-exclusive]");
  if (!ticketBlock) {
    return { ok: false, error: "Bloc billet parent introuvable", added: null };
  }

  const getControls = () => {
    const buttons = [...ticketBlock.querySelectorAll("button")];
    const plusButton = buttons.find(b => (b.innerText || b.textContent || "").trim() === "+");
    const minusButton = buttons.find(b => ["−", "-"].includes((b.innerText || b.textContent || "").trim()));
    const quantityContainer = plusButton?.parentElement || ticketBlock;
    const quantitySpan = [...quantityContainer.querySelectorAll("span")]
      .find(s => /^\\d+$/.test(s.innerText.trim()));

    return { plusButton, minusButton, quantitySpan };
  };

  let added = 0;
  let displayedQuantity = null;

  while (true) {
    if (ticketTimeoutMs > 0 && Date.now() - startedAt >= ticketTimeoutMs) {
      return {
        ok: false,
        error: `Timeout comptage ticket après ${Math.round(ticketTimeoutMs / 1000)}s`,
        warning: "TIMEOUT_TICKET",
        added,
        displayedQuantity
      };
    }

    const { plusButton, quantitySpan } = getControls();
    if (!plusButton) {
      const blockText = norm(ticketBlock.innerText);

      return {
        ok: true,
        added: 0,
        displayedQuantity: null,
        status: blockText.includes("épuisé") || blockText.includes("epuise") || blockText.includes("sold")
          ? "sold_out"
          : "not_available",
        warning: null
      };
    }

    if (isDisabled(plusButton)) {
      break;
    }

    const before = quantitySpan ? quantitySpan.innerText.trim() : null;
    plusButton.click();

    await sleep(delayMs);

    const after = quantitySpan ? quantitySpan.innerText.trim() : null;
    displayedQuantity = after;

    if (quantitySpan && before === after) {
      break;
    }

    added++;

    if (debug && progressEvery && added % progressEvery === 0) {
      console.log(`[shotgun-debug] ${ticketName}: ${added} clics +`);
    }

    if (maxClicks > 0 && added >= maxClicks) {
      return {
        ok: true,
        warning: "MAX_CLICKS atteint",
        added,
        displayedQuantity
      };
    }
  }

  return { ok: true, added, displayedQuantity };
}
"""


async def open_ticket_panel(page):
    # 1. Si les tickets sont déjà présents, rien à ouvrir.
    ticket_blocks_count = await page.evaluate(
        """
        () => document.querySelectorAll("[data-exclusive]").length
        """
    )

    if ticket_blocks_count > 0:
        return True

    # 2. Cherche uniquement des éléments cliquables plausibles.
    clicked = await page.evaluate(
        """
        () => {
          const norm = s => (s || "").toLowerCase().replace(/\\s+/g, " ").trim();

          const candidates = [
            ...document.querySelectorAll("button"),
            ...document.querySelectorAll("[role='button']"),
            ...document.querySelectorAll("a")
          ];

          const wanted = [
            "maintenant à",
            "now from",
            "acheter",
            "réserver",
            "reserver",
            "s'inscrire",
            "inscription",
            "gratuit",
            "maintenant",
            "billet",
            "tickets"
          ];

          for (const el of candidates) {
            const text = norm(el.innerText || el.textContent);
            const href = el.getAttribute("href") || "";
            const className = String(el.className || "");

            if (!text) continue;
            if (className.includes("Cookiebot") || href.includes("partners-cookies")) continue;

            if (wanted.some(w => text.includes(w))) {
              el.click();
              return {
                ok: true,
                text
              };
            }
          }

          return {
            ok: false,
            text: null
          };
        }
        """
    )

    if clicked["ok"]:
        await page.wait_for_timeout(3000)

    # 3. Vérifie si les tickets sont apparus après le clic.
    ticket_blocks_count = await page.evaluate(
        """
        () => document.querySelectorAll("[data-exclusive]").length
        """
    )

    return ticket_blocks_count > 0


async def accept_cookies(page):
    selectors = [
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "#CybotCookiebotDialogBodyButtonAccept",
        "#CybotCookiebotDialogBodyButtonDecline",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                await locator.first.click(timeout=2000)
                await page.wait_for_timeout(500)
                return
        except Exception:
            pass

    for text in [
        "TOUT AUTORISER",
        "Tout autoriser",
        "Accepter",
        "J'accepte",
        "Tout accepter",
        "Accept",
        "REFUSER",
        "Refuser",
    ]:
        try:
            btn = page.get_by_role("button", name=text)
            if await btn.count() > 0:
                await btn.first.click(timeout=2000)
                await page.wait_for_timeout(500)
                return
        except Exception:
            pass


async def scrape_event_tickets(event_url: str, debug: bool = False) -> list[dict]:
    max_clicks = get_int_env("SHOTGUN_MAX_CLICKS", DEFAULT_MAX_CLICKS)
    ticket_timeout = get_int_env(
        "SHOTGUN_TICKET_TIMEOUT_SECONDS",
        DEFAULT_TICKET_TIMEOUT_SECONDS,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            locale="fr-FR",
            viewport={"width": 1400, "height": 1200},
        )

        page = await context.new_page()

        if debug:
            page.on(
                "console",
                lambda message: print(message.text, flush=True)
                if message.text.startswith("[shotgun-debug]")
                else None,
            )

        if debug:
            print(f"[debug] Chargement page: {event_url}", flush=True)

        await page.goto(event_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        if debug:
            print("[debug] Gestion cookies", flush=True)

        await accept_cookies(page)
        await page.wait_for_timeout(1000)

        if debug:
            print("[debug] Ouverture panneau billets", flush=True)

        opened = await open_ticket_panel(page)
        if not opened:
            if debug:
                print("[debug] Panneau billets introuvable", flush=True)

            await browser.close()
            return [
                {
                    "event_url": event_url,
                    "ticket_name": None,
                    "available_count": None,
                    "ok": False,
                    "error": "Impossible d'ouvrir le panneau billets",
                    "warning": None,
                }
            ]

        await page.wait_for_timeout(3000)

        ticket_names = await page.evaluate(
            """
            () => {
            const norm = s => (s || "").replace(/\\s+/g, " ").trim();

            return [...document.querySelectorAll("h3")]
                .filter(h => h.closest("[data-exclusive]"))
                .map(h => norm(h.innerText))
                .filter(Boolean);
            }
            """
        )

        if debug:
            print(f"[debug] Tickets trouvés: {', '.join(ticket_names)}", flush=True)

        results = []

        for index, ticket_name in enumerate(ticket_names):
            if debug:
                print(
                    f"[debug] Comptage ticket: {ticket_name} "
                    f"(max_clicks={max_clicks or 'unlimited'}, timeout={ticket_timeout}s)",
                    flush=True,
                )

            try:
                result = await asyncio.wait_for(
                    page.evaluate(
                        JS_COUNT_SCRIPT,
                        {
                            "ticketName": ticket_name,
                            "delayMs": 2,
                            "maxClicks": max_clicks,
                            "debug": debug,
                            "progressEvery": 100,
                            "ticketTimeoutMs": ticket_timeout * 1000,
                        },
                    ),
                    timeout=ticket_timeout + 10,
                )
            except asyncio.TimeoutError:
                result = {
                    "ok": False,
                    "added": None,
                    "error": f"Timeout comptage ticket après {ticket_timeout}s",
                    "warning": "TIMEOUT_TICKET",
                    "displayedQuantity": None,
                }

            if debug:
                print(
                    "[debug] Résultat ticket: "
                    f"{ticket_name} | added={result.get('added')} | "
                    f"warning={result.get('warning')}",
                    flush=True,
                )

            results.append(
                {
                    "event_url": event_url,
                    "ticket_name": ticket_name,
                    "available_count": result.get("added"),
                    "ok": bool(result.get("ok")),
                    "error": result.get("error"),
                    "warning": result.get("warning"),
                    "displayed_quantity": result.get("displayedQuantity"),
                }
            )

            if result.get("added") and index < len(ticket_names) - 1:
                if debug:
                    print("[debug] Rechargement page pour panier propre", flush=True)

                await page.reload(wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(1000)
                await open_ticket_panel(page)
                await page.wait_for_timeout(1000)

        await browser.close()
        return results
