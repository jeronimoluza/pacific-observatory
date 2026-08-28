"""DEPS Brunei — Monthly Average Retail Price of Selected Food / Non-Food Items.

Source: Department of Economic Planning and Statistics (DEPS), Ministry of
Finance and Economy — https://deps.mofe.gov.bn/edl-consumer-price-index-economy/
("eData Library"). Two XLSX downloads (food items, non-food items), same
wide year x month layout, merged into one official_avg PriceObservation feed.

The page's <a href> to the XLSX is stale by design — WordPress re-uploads
the file under a new /wp-content/uploads/<year>/<month>/ path every time
DEPS refreshes it, so a hardcoded path goes 404 within weeks. Resolve the
current path via the (open) WP REST API media search instead.
"""

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_MEDIA_SEARCH_URL = "https://deps.mofe.gov.bn/wp-json/wp/v2/media"
_SITE_ORIGIN = "https://deps.mofe.gov.bn"
_COUNTRY = "Brunei Darussalam"
_CURRENCY = "BND"
_SOURCE_KEY = "bn_deps_arp"

_REPORT_TITLES = [
    "Monthly-Average-Retail-Price-of-Selected-Food-Items",
    "Monthly-Average-Retail-Price-of-Selected-Non-Food-Items",
]

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_UNIT_RE = re.compile(r"\(([^()]+)\)\s*$")

_IDENT = ["source_key", "observation_date", "item_name"]


def _resolve_media_url(session, title: str) -> str | None:
    """WP REST API media search — current file path, not the stale page href."""
    resp = session.get(
        _MEDIA_SEARCH_URL, params={"search": title, "per_page": 5}, timeout=30
    )
    resp.raise_for_status()
    results = resp.json()
    for item in results:
        guid = item.get("guid", {}).get("rendered", "")
        if title.lower() in guid.lower():
            return _SITE_ORIGIN + guid if guid.startswith("/") else guid
    return None


def _year_month_columns(df: pd.DataFrame) -> dict[int, tuple[int, int]]:
    """Map column index -> (year, month) from the forward-filled year row
    and the per-column month-name row directly below it."""
    year_row_idx = None
    for r in range(min(8, len(df))):
        years = [
            v
            for v in df.iloc[r].tolist()
            if isinstance(v, (int, float)) and 2000 <= v <= 2100
        ]
        if len(years) >= 2:
            year_row_idx = r
            break
    if year_row_idx is None:
        return {}, None
    month_row = df.iloc[year_row_idx + 1]

    col_map: dict[int, tuple[int, int]] = {}
    current_year = None
    for c in range(1, df.shape[1]):
        yval = df.iat[year_row_idx, c]
        if isinstance(yval, (int, float)) and 2000 <= yval <= 2100:
            current_year = int(yval)
        mval = month_row.iloc[c]
        if isinstance(mval, str) and mval.strip().lower() in _MONTHS and current_year:
            col_map[c] = (current_year, _MONTHS[mval.strip().lower()])
    return col_map, year_row_idx + 1


def _parse_wide_table(df: pd.DataFrame, cutoff: date) -> list[dict]:
    col_map, month_row_idx = _year_month_columns(df)
    if not col_map:
        logger.warning("Could not locate year/month header rows in DEPS ARP sheet")
        return []

    rows = []
    for r in range(month_row_idx + 1, len(df)):
        item_name = df.iat[r, 0]
        if not isinstance(item_name, str) or not item_name.strip():
            continue
        item_name = item_name.strip()

        unit_match = _UNIT_RE.search(item_name)
        unit = unit_match.group(1).strip() if unit_match else None

        for c, (year, month) in col_map.items():
            raw = df.iat[r, c]
            if pd.isna(raw):
                continue
            try:
                price = float(raw)
            except (TypeError, ValueError):
                continue
            obs_date = date(year, month, 1)
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": price,
                "currency": _CURRENCY,
                "unit": unit,
                "source_url": _SITE_ORIGIN + "/edl-consumer-price-index-economy/",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_bn_deps_arp(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    all_rows: list[dict] = []

    for title in _REPORT_TITLES:
        url = _resolve_media_url(session, title)
        if not url:
            logger.warning(
                "DEPS ARP: could not resolve current media URL for %r", title
            )
            continue
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        df = pd.read_excel(BytesIO(resp.content), sheet_name="Data", header=None)
        all_rows.extend(_parse_wide_table(df, cutoff))

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
