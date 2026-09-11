"""tarkari.com.np -- Nepal vegetable/fruit market-price list.

Single static HTML table at /oracle/marketprice_list/, parsed with
pandas.read_html (lowest-effort extractor per the fetcher-pattern doc's
extraction_pattern: html_scrape guidance). Columns: Product, Unit, Min (Rs),
Avg (Rs), Max (Rs), Date.

Verified live 2026-09-11: 101 rows, 97 distinct product/variety names
(Tomato Big(Nepali), Potato Red(Indian), Onion Dry(Indian), ...), spanning
only 3 distinct release dates (2026-05-01, 2026-05-22, 2026-07-07) -- this
reads as an occasionally-updated snapshot page, not a live daily feed (the
page carries no pagination or date picker; the whole history it has ever
published is on this one page). Still onboarded: it clears the >=5-row gate
by a wide margin and is the only market-level fresh-produce price list found
for Nepal in this sweep.

`Avg (Rs)` is emitted as price_local (the page's own Min/Max columns are
dropped as derived/non-independent, same convention as gy_moa_market_prices).

coicop_classification: classifier -- item names span many COICOP-01
subclasses (vegetables today; the page schema does not preclude other
produce types later), so coicop_codes is left unset.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.tarkari.com.np/oracle/marketprice_list/"
_COUNTRY = "Nepal"
_SOURCE_KEY = "tarkari_com_np"
_CURRENCY = "NPR"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]


def _parse_date(text: str) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def fetch_tarkari_com_np(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_URL, timeout=30)
        resp.raise_for_status()
    except Exception:
        logger.exception("[%s] Failed to fetch %s", _SOURCE_KEY, _URL)
        return None

    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError:
        logger.warning("[%s] No HTML table found at %s", _SOURCE_KEY, _URL)
        return None
    if not tables:
        return None
    table = tables[0]

    required = {"Product", "Unit", "Avg (Rs)", "Date"}
    if not required.issubset(table.columns):
        logger.warning("[%s] Unexpected table columns: %s", _SOURCE_KEY, list(table.columns))
        return None

    rows = []
    for _, r in table.iterrows():
        obs_date = _parse_date(str(r["Date"]))
        if obs_date is None or obs_date <= cutoff:
            continue
        item_name = str(r["Product"]).strip()
        unit = str(r["Unit"]).strip()
        price_raw = r["Avg (Rs)"]
        try:
            price_local = float(price_raw)
        except (TypeError, ValueError):
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": unit,
            "subnational_area": None,
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
