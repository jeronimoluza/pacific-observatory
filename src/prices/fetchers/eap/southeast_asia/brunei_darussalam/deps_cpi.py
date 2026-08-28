"""DEPS Brunei — Monthly Consumer Price Index (12-division grouping).

Source: Department of Economic Planning and Statistics (DEPS), Ministry of
Finance and Economy — https://deps.mofe.gov.bn/edl-consumer-price-index-economy/
("eData Library"), Monthly-Consumer-Price-Index.xlsx. Sibling of
deps_arp.py (average retail prices) but a distinct row schema
(IndexObservation) — kept as a separate fetcher and manifest per the
official_avg / cpi_benchmark split.

Same stale-href problem as deps_arp.py: resolve the current file path via
the open WP REST API media search rather than the page's hardcoded href.
"""

import logging
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_MEDIA_SEARCH_URL = "https://deps.mofe.gov.bn/wp-json/wp/v2/media"
_SITE_ORIGIN = "https://deps.mofe.gov.bn"
_REPORT_TITLE = "Monthly-Consumer-Price-Index"
_COUNTRY = "Brunei Darussalam"
_SOURCE_KEY = "bn_deps_cpi"


def _base_period_for_year(year: int) -> str:
    """DEPS rebased the series in 2015 (footnote on the 'Data' sheet:
    Jan 2010=100 for 2010-2014, Jan 2015=100 for 2015 onward)."""
    return "January 2010=100" if year < 2015 else "January 2015=100"


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

# Publisher's 12-group breakdown (COICOP-1999 style) -> COICOP-2018 2-digit
# division. "Overall CPI" (the all-items headline) is intentionally NOT
# emitted: IndexObservation requires coicop_code and there is no sanctioned
# sentinel for the headline series yet (see SKILL.md "Open design questions").
# COICOP 02 (Alcohol & Tobacco) is absent from the publisher's breakdown -
# most likely folded into Miscellaneous, per the SingStat precedent.
_DIVISION_MAP = {
    "Food and Non-Alcoholic Beverages": "01",
    "Clothing and Footwear": "03",
    "Housing, Water, Electricity, Gas and Other Fuels": "04",
    "Furnishing, Household Equipment and Routine Household Maintenance": "05",
    "Health": "06",
    "Transport": "07",
    "Communication": "08",
    "Recreation and Culture": "09",
    "Education": "10",
    "Restaurants and Hotels": "11",
    "Miscellaneous Goods and Services": "12",
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _resolve_media_url(session, title: str) -> str | None:
    resp = session.get(
        _MEDIA_SEARCH_URL, params={"search": title, "per_page": 5}, timeout=30
    )
    resp.raise_for_status()
    results = resp.json()
    for item in results:
        guid = item.get("guid", {}).get("rendered", "")
        # Exact match only - the search also returns the "of Goods
        # According to Durability" and "Percentage-Change" siblings.
        if (
            title.lower() in guid.lower()
            and "durability" not in guid.lower()
            and "percentage" not in guid.lower()
            and "food-and-non-food" not in guid.lower()
        ):
            return _SITE_ORIGIN + guid if guid.startswith("/") else guid
    return None


def _year_month_columns(df: pd.DataFrame):
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


def fetch_bn_deps_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    url = _resolve_media_url(session, _REPORT_TITLE)
    if not url:
        logger.warning("DEPS CPI: could not resolve current media URL")
        return None
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(BytesIO(resp.content), sheet_name="Data", header=None)

    col_map, month_row_idx = _year_month_columns(df)
    if not col_map:
        logger.warning("Could not locate year/month header rows in DEPS CPI sheet")
        return None

    rows = []
    for r in range(month_row_idx + 1, len(df)):
        label = df.iat[r, 0]
        if not isinstance(label, str):
            continue
        label = label.strip()
        coicop = _DIVISION_MAP.get(label)
        if not coicop:
            if label and label != "Overall CPI":
                logger.warning(
                    "No COICOP mapping for DEPS CPI division %r — dropping row", label
                )
            continue

        for c, (year, month) in col_map.items():
            raw = df.iat[r, c]
            if pd.isna(raw):
                continue
            try:
                idx_val = float(raw)
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
                "coicop_code": coicop,
                "index_value": idx_val,
                "index_base_period": _base_period_for_year(year),
                "source_url": _SITE_ORIGIN + "/edl-consumer-price-index-economy/",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
