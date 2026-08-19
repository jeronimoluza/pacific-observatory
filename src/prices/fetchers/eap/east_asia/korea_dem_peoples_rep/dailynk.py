"""Daily NK — informal-market rice price monitor (North Korea).

Daily NK (Seoul-based DPRK-focused news outlet, part of Unification Media
Group) maintains a "Rice Prices" data page built from its in-country
informal-market source network — the closest thing to a price-level series
that exists for North Korea, which has no scrapeable retail/e-commerce
channel at all. Unlike the rest of the site (narrative articles), this page
is a genuine recurring data series: the price table and per-city line charts
are rendered client-side from a JS array literal (``const RP_DATA = [...]``)
embedded directly in the page HTML, with clean numeric ``date/p/s/h`` fields
per row (KPW per kg for Pyongyang/Sinuiju/Hyesan) reaching back to 2009,
reported roughly biweekly. There is no JSON API backing it; the array is
parsed out of the raw HTML via regex.

Narrow single-commodity source: every row carries COICOP 01.1.1.1.2 (Rice).
Prices are consistently KPW/kg on this page — no CNY/USD rows observed here
(unlike some DPRK informal-market reporting elsewhere), so currency is a
fixed constant, not a per-row field.

The page reports three reference markets per date (Pyongyang, Sinuiju,
Hyesan). Following the precedent in ``_shared.eap.wfp_food_prices``
(per-market rows collapsed to a national average, market spread kept in
``notes``), this fetcher emits one national row per date: the mean of the
three cities, with the individual city prices recorded in ``notes``.
``subnational_area`` is therefore None — the row is a national aggregate,
not a city observation. ``PRICE_COLUMNS`` does now carry that column, so
switching to one row per city is a one-line change plus adding the field to
``_IDENT``; that is a data-modelling decision, not a defect.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.dailynk.com/english/north-korea-market-trends-rice/"
_COUNTRY = "Korea, Dem. People's Rep."
_CURRENCY = "KPW"
_SOURCE_KEY = "kp_dailynk"
_COICOP_CODE = "01.1.1.1.2"
_ITEM_NAME = "Rice"
_UNIT = "kg"
_IDENT = ["source_key", "observation_date", "item_name"]

_ARRAY_RE = re.compile(r"const RP_DATA = (\[.*?\]);", re.S)
_ROW_RE = re.compile(
    r'date:"(\d{4}-\d{2}-\d{2})"\s*,\s*p:\s*(\d+)\s*,\s*s:\s*(\d+)\s*,\s*h:\s*(\d+)\s*\}'
)


def fetch_kp_dailynk(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=60)
    resp.raise_for_status()

    array_match = _ARRAY_RE.search(resp.text)
    if not array_match:
        logger.warning("[%s] RP_DATA array not found on page", _SOURCE_KEY)
        return None
    matches = _ROW_RE.findall(array_match.group(1))
    if not matches:
        logger.warning("[%s] RP_DATA found but no rows parsed", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for raw_date, p, s, h in matches:
        obs_date = date.fromisoformat(raw_date)
        if obs_date <= cutoff:
            continue
        prices = [float(x) for x in (p, s, h) if 0 < float(x) < 1e9]
        if not prices:
            continue
        avg_price = round(sum(prices) / len(prices), 2)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": _ITEM_NAME,
            "price_local": avg_price,
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _URL,
            "notes": (
                f"national avg of 3 reference markets, KPW/kg — "
                f"Pyongyang={p}, Sinuiju={s}, Hyesan={h}; "
                "via Daily NK in-country source network"
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
