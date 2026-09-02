"""SIB (Statistical Institute of Belize) -- Monthly Consumer Price Index.

sib.org.bz publishes the CPI page via a WordPress "resources" widget whose
document list is itself loaded by client-side JS from a JSON endpoint
(discovered via a Playwright network trace, not linked anywhere in the
static HTML):

    https://sib.org.bz/wp-json/sibr/v1/resources?type=document&page=1&per_page=12&topic=consumer-price-index-statistics

That endpoint returns a "Monthly Consumer Price Index" entry whose `files[0]
.dl` is a stable download redirect (`https://sib.org.bz/dl/monthly-
consumer-price-index/`) to the current XLSX -- filename-free, so no
month-guessing needed.

The XLSX ("EXTENDED SERIES" sheet) is a single wide table, October 2020=100,
COICOP 2018, monthly from Nov 1990 to the latest published month (Jul 2026
as of 2026-09-01). Layout is irregular, not a clean rectangular frame:
year values appear alone in column 1 on their own row (all other columns
NaN), followed by one row per published month in that year (column 1 holds
the 3-letter month abbrev, columns 2-15 hold the index values), blank rows
separate years, and the table ends with a "Source: ..." row followed by a
revision-note row -- both must be excluded from parsing.

Column 2 ("All Items", the headline index) is intentionally NOT emitted:
IndexObservation requires `coicop_code`, and there is no sanctioned
sentinel for headline CPI yet (see onboarding skill's open design
questions). Columns 3-15 map 1:1, in order, onto COICOP 2018 divisions
01-13 -- SIB's own division labels already follow the COICOP 2018 grouping
exactly, no translation table needed.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_RESOURCES_URL = (
    "https://sib.org.bz/wp-json/sibr/v1/resources"
    "?type=document&page=1&per_page=12&topic=consumer-price-index-statistics"
)
_FALLBACK_DL_URL = "https://sib.org.bz/dl/monthly-consumer-price-index/"
_COUNTRY = "Belize"
_SOURCE_KEY = "bz_sib_cpi"
_BASE_PERIOD = "October 2020=100"
_SHEET_NAME = "EXTENDED SERIES"

# Column index (0-based, as read by pandas with header=None) -> COICOP 2018
# division. Column 2 (All Items / headline) is deliberately excluded.
_COLUMN_COICOP = {
    3: "01",
    4: "02",
    5: "03",
    6: "04",
    7: "05",
    8: "06",
    9: "07",
    10: "08",
    11: "09",
    12: "10",
    13: "11",
    14: "12",
    15: "13",
}

_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _discover_download_url(session) -> str:
    try:
        resp = session.get(_RESOURCES_URL, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload.get("items", []):
            if item.get("title") == "Monthly Consumer Price Index":
                for f in item.get("files", []):
                    if f.get("dl"):
                        return f["dl"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] resource-list discovery failed: %s", _SOURCE_KEY, exc)
    return _FALLBACK_DL_URL


def fetch_bz_sib_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    dl_url = _discover_download_url(session)
    resp = session.get(dl_url, timeout=60)
    resp.raise_for_status()

    df = pd.read_excel(io.BytesIO(resp.content), sheet_name=_SHEET_NAME, header=None)

    rows = []
    current_year: int | None = None
    for _, r in df.iterrows():
        col1 = r[1]
        if pd.isna(col1):
            continue
        if isinstance(col1, (int, float)) and 1900 < col1 < 2100:
            current_year = int(col1)
            continue
        month_key = str(col1).strip().upper()
        if month_key not in _MONTHS or current_year is None:
            continue  # "Source: ..." / revision-note rows, or malformed
        obs_date = date(current_year, _MONTHS[month_key], 1)
        if obs_date <= cutoff:
            continue
        for col_idx, coicop in _COLUMN_COICOP.items():
            value = r.get(col_idx)
            if pd.isna(value):
                continue
            try:
                index_value = float(value)
            except (TypeError, ValueError):
                logger.warning(
                    "[%s] non-numeric index value %r for %s %s -- dropping row",
                    _SOURCE_KEY,
                    value,
                    obs_date,
                    coicop,
                )
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": index_value,
                "index_base_period": _BASE_PERIOD,
                "source_url": dl_url,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
