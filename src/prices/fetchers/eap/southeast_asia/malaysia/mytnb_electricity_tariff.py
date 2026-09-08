"""Tenaga Nasional Berhad (TNB) — regulated electricity tariff, Malaysia.

TNB's public tariff page (mytnb.com.my/tariff) is an Angular SPA -- the raw
HTML ships almost no content, so this fetcher renders with Playwright (6s
settle) rather than fetching the URL directly. Once hydrated, the page
holds ~30 HTML tables covering every customer class (Domestic, Non-Domestic
Low/Medium/High Voltage, Agriculture, Water & Sewerage Operator, Street
Lighting, Traction, Bulk, TES, Backfeed, Ultra High Voltage). This fetcher
takes only the "Domestic General Tariff" / "Domestic ToU Tariff" table --
the one that prices household electricity, COICOP 04.5.1 -- and skips the
rest; they are all commercial/industrial/institutional customer classes,
each of which would need its own onboarding judgment call rather than being
swept in for free.

Row structure inside that table: a bare 1-cell row states the tariff plan
name ("Domestic General Tariff" / "Domestic ToU Tariff"), the next bare
1-cell row states the consumption tier ("For total consumption 1,500 kWh
and below per month" / "... more than 1,500 kWh per month"), then several
3-cell charge rows (label, unit, value) follow until the next plan/tier
header or a "Note:" row. Plan and tier are tracked as running state while
walking <tr> rows in document order.

Charges are published in sen (1/100 MYR) for per-kWh rates and in whole RM
for the flat monthly retail charge -- price_local is normalized to whole
MYR by dividing sen values by 100, same pattern as the Fiji/EFL cents
fetcher.

Verified live 2026-09-06: 18 rows, effective_from 2025-07-01 ("New Rates
(1 July 2025)" stamped in the page's own column header).

Gotcha: an earlier "Old Tariff Category -> New Tariff Category" mapping
table ALSO contains the bullet text "Domestic General Tariff" (as a label
inside its mapping cell), so a naive "table containing this text" search
grabs that table instead of the real rate table and silently yields zero
rows. The selector below additionally requires "Energy Charge" to appear,
which only the real rate table has.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_TARIFF_URL = "https://www.mytnb.com.my/tariff/index.html?lang=en"
_COUNTRY = "Malaysia"
_CURRENCY = "MYR"
_SOURCE_KEY = "my_mytnb_electricity_tariff"
_COICOP = "04.5.1.0"

_IDENT = ["source_key", "effective_from", "item_name"]

_EFFECTIVE_RE = re.compile(
    r"New Rates\s*\(\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*\)", re.I
)

_UNIT_MAP = {
    "sen/kwh": ("kWh", 0.01),
    "rm/month": ("month", 1.0),
    "rm/kw": ("kW", 1.0),
}


def _render_html() -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.goto(_TARIFF_URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        html = page.content()
        browser.close()
    return html


def fetch_my_mytnb_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    html = _render_html()
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    m = _EFFECTIVE_RE.search(text)
    if not m:
        logger.warning("[%s] Could not parse effective date", _SOURCE_KEY)
        return None
    day, month_name, year = m.groups()
    effective_from = pd.to_datetime(f"{day} {month_name} {year}", format="%d %B %Y").date()

    if effective_from <= cutoff:
        logger.info("[%s] No new data since cutoff %s", _SOURCE_KEY, cutoff)
        return None

    domestic_table = next(
        (
            t
            for t in soup.find_all("table")
            if "Domestic General Tariff" in t.get_text() and "Energy Charge" in t.get_text()
        ),
        None,
    )
    if domestic_table is None:
        logger.warning("[%s] Could not find the Domestic tariff table", _SOURCE_KEY)
        return None

    plan, tier = None, None
    parsed_rows: list[dict] = []
    for tr in domestic_table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not cells or cells[0].startswith("Note:"):
            continue
        if len(cells) == 1 or all(not c for c in cells[1:]):
            label = cells[0]
            if "Tariff" in label:
                plan = label
            elif "consumption" in label.lower():
                tier = label
            continue
        if len(cells) < 3:
            continue
        label, unit_text, value_text = cells[0], cells[1], cells[2]
        mapped = _UNIT_MAP.get(unit_text.strip().lower())
        if mapped is None:
            continue
        unit, scale = mapped
        try:
            value = float(value_text.replace(",", "")) * scale
        except ValueError:
            continue
        parsed_rows.append(
            {
                "item_name": f"{plan} – {tier} – {label}",
                "price_local": round(value, 6),
                "unit": unit,
            }
        )

    rows = []
    for item in parsed_rows:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": _TARIFF_URL,
            "notes": "TNB-published regulated domestic electricity tariff (government-approved).",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
