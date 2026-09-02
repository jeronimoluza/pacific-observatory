"""Orange Sierra Leone -- prepaid data bundle tariffs.

Orange SL (orange.sl) publishes its mobile data-bundle catalog as
server-rendered "offer variant" cards embedding a plain-text description
list (Quantity / Validity / Price) per bundle -- no JS rendering required.
Covers Monthly, Weekly and Daily data-bundle pages.

Emits PriceObservation rows (analytical_role: tariff, coicop_classification:
source_curated -> "08.3.0" telecommunication services).

CURRENCY TRAP: every price on this site is labelled "SLL" (e.g. "Price:
37.50 SLL" for a monthly 2.5GB bundle). Taken at face value that would be
the PRE-2022 legacy leone -- but the magnitudes are wrong for that reading:
a 20GB/month bundle prices at "300 SLL", and 100MB/week at "2 SLL". If these
were genuine pre-2022 SLL amounts they would convert to 0.3 and 0.002 new
leone (SLE) respectively -- i.e. a small fraction of one US cent for a data
bundle, which is not a plausible retail price anywhere. Cross-checked
against Africell SL's data-bundle tariffs scraped the same day (see
africell_tariffs.py): Africell's 15GB/30-day bundle is "NLe 300" -- the
SAME face-value number Orange shows for its 20GB/month bundle ("300 SLL").
That match is decisive: Orange's site still carries the pre-redenomination
"SLL" currency code as a stale label, but the numeric values it displays are
already in NEW leone (SLE) magnitude. All rows are emitted with
currency=SLE, and the raw displayed number is used unchanged (no /1000
rescale) -- only the currency CODE is corrected, not the magnitude.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_PAGES = {
    "https://www.orange.sl/en/b2c-internet-personal/data-bundles-monthly.html": "monthly",
    "https://www.orange.sl/en/b2c-internet-personal/data-bundles-weekly.html": "weekly",
    "https://www.orange.sl/en/b2c-internet-personal/data-bundle-daily.html": "daily",
}
_COUNTRY = "Sierra Leone"
_SOURCE_KEY = "sl_orange_tariffs"
_CURRENCY = "SLE"
_COICOP_MAP_DEFAULT = "08.3.0"
_IDENT = ["source_key", "item_name", "unit"]

_ITEM_RE = re.compile(
    r"data-dl_event_label=\"([^\"]+)\".*?"
    r">Quantity: ([^<]+)<.*?>Validity: ([^<]+)<.*?>Price: ([^<]+)<",
    re.DOTALL,
)
_NBSP_RE = re.compile(r"&nbsp;|\xa0")


def _clean_num(text: str) -> float | None:
    text = _NBSP_RE.sub(" ", text)
    m = re.search(r"[\d,.]+", text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_page(html: str, section_label: str) -> list[dict]:
    rows: list[dict] = []
    for label, quantity, validity, price_text in _ITEM_RE.findall(html):
        price = _clean_num(price_text)
        if price is None:
            continue
        quantity = _NBSP_RE.sub(" ", quantity).strip()
        validity = _NBSP_RE.sub(" ", validity).strip()
        item_name = f"Orange {section_label} {label.strip()} ({quantity}, {validity})"
        rows.append(
            {
                "item_name": item_name,
                "price_local": price,
                "unit": validity or "unspecified",
                "category": section_label,
            }
        )
    return rows


def fetch_sl_orange_tariffs(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    today = date.today()
    if today <= cutoff:
        return None

    parsed: list[dict] = []
    for url, section_label in _PAGES.items():
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as exc:
            logger.warning("[%s] Request failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, url)
            continue
        page_rows = _parse_page(resp.text, section_label)
        for r in page_rows:
            r["source_url"] = url
        parsed.extend(page_rows)

    if not parsed:
        logger.warning("[%s] No tariff rows parsed", _SOURCE_KEY)
        return None

    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": p["unit"],
            "coicop_code": _COICOP_MAP_DEFAULT,
            "source_url": p["source_url"],
            "notes": p["category"],
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
