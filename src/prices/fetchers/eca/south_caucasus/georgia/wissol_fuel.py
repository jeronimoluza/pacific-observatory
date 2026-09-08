"""Wissol Petroleum Georgia — retail fuel prices ("today's prices"), Georgia.

Discovery note: the seed host for this source was `smart.ge`, which turned
out to be Wissol's loyalty-card ("Smart") portal (Webflow-built,
`wissol-staging.css` asset, cross-links to `wissol.ge`) rather than a
standalone retailer. The real fuel-price page lives on the parent brand's
own domain, `wissol.ge/ka/fuel-prices` -- the classic "search for the real
domain before writing off a seed" pattern.

The rendered page also calls an internal JSON endpoint
(`https://api.wissol.ge/fuelpricehistory/?days=30`) for a 30-day price-
history chart, which would have been an even richer catch -- but that
subdomain's IP (185.36.244.137, distinct from the main site's) times out
at the TCP layer from this vantage point (same symptom as several other
hosts probed this run: DNS resolves, `curl`/`curl_cffi` connect hangs).
This fetcher does not depend on it; it reads the *current* prices straight
off the static page instead, which is enough to satisfy the ≥5-row bar on
its own and needs no daily backfill logic.

Each fuel product is rendered twice in the raw HTML (a card sighting plus
an expandable "details" popup) -- the popup containers
(`div.popup[id^="prices-"]`) are the ONLY reliably de-duplicated source of
one row per product; the plain `.prices_price` class appears 3-4x per
product across breakpoints and double-counts if used directly. Most
products publish both a "standard" price and a cheaper "self-service"
price at the same pump; both are emitted as separate rows.

Verified live 2026-09-06: 8 products, 14 rows (8 standard + 6 self-service;
the LPG line-item and the top-grade petrol line only publish one price
each). Mapped to the deepest COICOP leaves under 07.2.2: petrol grades ->
07.2.2.2, diesel grades -> 07.2.2.1, and the LPG ("ვისოლ გაზი" / Wissol Gas)
row -> 07.2.2.3 (Other fuels) -- this is pump auto-gas, not a household
cylinder-refill product.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_FUEL_PRICES_URL = "https://wissol.ge/ka/fuel-prices"
_COUNTRY = "Georgia"
_CURRENCY = "GEL"
_SOURCE_KEY = "ge_wissol_fuel"

# Deepest COICOP leaves under 07.2.2 (Fuels and lubricants for personal
# transport equipment): .1 Diesel, .2 Petrol, .3 Other fuels, .4 Lubricants.
# Wissol's 8 products are all petrol grades, diesel grades, or auto-LPG.
_COICOP_MAP = {
    "A1 სუპერი 100": "07.2.2.2",
    "ეკო სუპერი": "07.2.2.2",
    "ეკო პრემიუმი": "07.2.2.2",
    "ევრო რეგულარი": "07.2.2.2",
    "ეკო დიზელი": "07.2.2.1",
    "ევრო დიზელი": "07.2.2.1",
    "დიზელ ენერჯი": "07.2.2.1",
    "ვისოლ გაზი": "07.2.2.3",  # auto-LPG -- not diesel/petrol, not a household refill
}

_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"([\d.,]+)")


def _price_after_label(popup, label: str) -> float | None:
    """Find a <p> whose text starts with `label` and read the price from the
    NEXT <p> sibling -- the label and its value are separate DOM nodes, not
    one text run, so a flattened-text regex across them never matches."""
    label_p = popup.find("p", string=lambda s: bool(s) and s.strip().startswith(label))
    if label_p is None:
        return None
    value_p = label_p.find_next_sibling("p")
    if value_p is None:
        return None
    m = _PRICE_RE.search(value_p.get_text(strip=True))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def fetch_ge_wissol_fuel(cutoff: date) -> pd.DataFrame | None:
    observation_date = datetime.now(timezone.utc).date()
    if observation_date <= cutoff:
        logger.info("[%s] No new data since cutoff %s", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    resp = session.get(_FUEL_PRICES_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    popups = soup.select('div.popup[id^="prices-"]')
    if not popups:
        logger.warning("[%s] No fuel-price popup blocks found", _SOURCE_KEY)
        return None

    parsed_rows: list[dict] = []
    for popup in popups:
        parts = [p.strip() for p in popup.get_text(" | ", strip=True).split("|")]
        # First segment is the "დეტალები" (Details) toggle label; the product
        # name is the next non-empty segment.
        name = next((p for p in parts[1:] if p), None)
        if not name:
            continue

        coicop = _COICOP_MAP.get(name)
        if not coicop:
            logger.warning("No COICOP mapping for Wissol fuel product %r — dropping row", name)
            continue

        std_price = _price_after_label(popup, "სტანდარტული ფასი")
        if std_price is not None:
            parsed_rows.append(
                {"item_name": f"{name} (სტანდარტული / standard)", "price_local": std_price, "coicop": coicop}
            )

        ss_price = _price_after_label(popup, "თვითმომსახურების ფასი")
        if ss_price is not None:
            parsed_rows.append(
                {
                    "item_name": f"{name} (თვითმომსახურება / self-service)",
                    "price_local": ss_price,
                    "coicop": coicop,
                }
            )

    rows = []
    for item in parsed_rows:
        row = {
            "observation_date": observation_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": "L",
            "coicop_code": item["coicop"],
            "source_url": _FUEL_PRICES_URL,
            "notes": "Wissol Petroleum Georgia posted retail pump price, read live off the public price page.",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
