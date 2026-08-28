"""Sri Lanka DCS (Department of Census & Statistics) — Weekly Retail Prices.

Government weekly retail price series (absolute prices, not an index),
collected across 14 markets in the Colombo district. The dashboard's data
source is a raw JS data file, not a JSON API: re-verified live 2026-08-06,
GET https://www.statistics.gov.lk/DashBoard/Prices/Prices_Data.php -> 200,
1.85MB body containing `var pip=[...]` (122 named products with category)
and `var prices=[...]` (456 weekly rows, one dict per week keyed by product
code, back to 2017). Sample: 'Ash Plantain  1kg' (Low Country Vegetables),
week 'W4.June.2026' price 281.43 LKR.

Missing values are written as the invalid-JSON literal `''` (single-quoted
empty string) rather than `null`, so the raw JS array text is cleaned before
`json.loads`. Week labels are `W<n>.<Month>.<Year>` (month spelled either
abbreviated or in full across the file's history) and are converted to an
approximate date (first day of month + (n-1) weeks) since no exact day is
published.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.statistics.gov.lk/DashBoard/Prices/Prices_Data.php"
_COUNTRY = "Sri Lanka"
_CURRENCY = "LKR"
_SOURCE_KEY = "lk_dcs_weekly_retail"
_IDENT = ["source_key", "observation_date", "item_name"]

_PIP_RE = re.compile(r"var pip\s*=\s*(\[.*?\]);", re.S)
_PRICES_RE = re.compile(r"var prices\s*=\s*(\[.*?\]);", re.S)
_WEEK_RE = re.compile(r"W(\d+)\.([A-Za-z]+)\.(\d{4})")

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _parse_week(label: str) -> date | None:
    m = _WEEK_RE.match(label.strip())
    if not m:
        return None
    week_no, month_txt, year_txt = m.groups()
    month = _MONTHS.get(month_txt.strip().lower())
    if not month:
        return None
    try:
        base = date(int(year_txt), month, 1)
    except ValueError:
        return None
    return base + timedelta(weeks=int(week_no) - 1)


def _load_arrays(text: str) -> tuple[list[dict], list[dict]] | None:
    m_pip = _PIP_RE.search(text)
    m_prices = _PRICES_RE.search(text)
    if not m_pip or not m_prices:
        return None
    try:
        pip = json.loads(m_pip.group(1))
    except ValueError:
        logger.warning("[%s] pip array not valid JSON", _SOURCE_KEY)
        return None
    prices_txt = re.sub(r":\s*''", ":null", m_prices.group(1))
    try:
        prices = json.loads(prices_txt)
    except ValueError:
        logger.warning("[%s] prices array not valid JSON after cleanup", _SOURCE_KEY)
        return None
    return pip, prices


def _rows(pip: list[dict], prices: list[dict], cutoff: date) -> list[dict]:
    meta = {
        p["product"]: (p.get("name", p["product"]).strip(), p.get("category"))
        for p in pip
        if p.get("product")
    }
    ts = get_scrape_ts()
    out: list[dict] = []
    for week in prices:
        label = week.get("Date")
        obs_date = _parse_week(label) if label else None
        if obs_date is None or obs_date <= cutoff:
            continue
        for code, value in week.items():
            if code == "Date" or value is None:
                continue
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if not 0 < price < 1_000_000:
                continue
            name, category = meta.get(code, (code, None))
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "weekly",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": name,
                "price_local": round(price, 2),
                "currency": _CURRENCY,
                "unit": None,
                "source_url": _URL,
                "notes": f"category={category}" if category else "",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)
    return out


def fetch_lk_dcs_weekly_retail(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_URL, timeout=90)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] fetch failed: %s", _SOURCE_KEY, exc)
        return None
    resp.encoding = resp.apparent_encoding or "utf-8"
    arrays = _load_arrays(resp.text)
    if not arrays:
        return None
    pip, prices = arrays
    rows = _rows(pip, prices, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
