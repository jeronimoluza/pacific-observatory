"""Agency on Statistics under the President of the RT -- monthly CPI by division.

stat.tj (WordPress) publishes an "Analytical tables" page
(https://www.stat.tj/en/analytical-tables/) with plain download links to
XLSX workbooks -- no anti-bot, no JS rendering. This fetcher targets
"CPI by 546 Items, 2015-<latest>" (filename changes year-to-year, e.g.
cpi_by_546_items_2015-en.xlsx), a single wide sheet (header=None, "Лист1")
laid out as: column A = a Russian/English (machine-translated) item or
group label at any of several indent levels (division -> group -> item),
and a strip of value columns per year: one bare year-int column (no data
under it) followed by 12 month-name columns (Jan..Dec) of month-over-
month index values (source base is "previous month = 100", not a fixed
calendar-year base -- values cluster around 100, e.g. 99.5-105).

Column headers are not always clean English month names: 2024/2025 carry
"Oktovber"/"Desember" typos for Oct/Dec, and one stray data cell for
Apr-2026 in the top "All goods and services" row contains the literal
Cyrillic string "Апрел" instead of a number where the source has not yet
published that month for that row -- both are handled by
_MONTH_ALIASES / a non-numeric-value skip, matching the tolerant-parse
approach in bz_sib_cpi.py.

Only the 12 division-aggregate rows are emitted (COICOP 2018 divisions
01-12; there is no division-13 aggregate in this domestic CPI basket).
Each row is matched by its exact (stripped) label text, not by a
hardcoded row number, because the workbook is re-uploaded yearly with
rows shifting as new items are added beneath each division. The ~500
item/subgroup rows nested under each division header are intentionally
dropped -- same "aggregate columns only, no item-level detail" scope
choice as bz_sib_cpi.py's headline SIB workbook.

Division label match text (as of the 2026-07 upload) -> COICOP:
  "Food on (without alcoholic beverages and tobacco products)" -> 01
  "Alcoholic beverages and tobacco products"                   -> 02
  "Clothing and footwear (including repairs)"                  -> 03
  "Housing and communal services"                              -> 04
  "Household items, household equipment and routine household
   maintenance"                                                -> 05
  "health Care"                                                -> 06
  "transport"                                                  -> 07
  "relationship" (machine-translation of "связь" / communication) -> 08
  "Leisure, entertainment and culture"                         -> 09
  "education" (source cell has leading non-breaking spaces)    -> 10
  "Restaurants and hotels"                                     -> 11
  "Miscellaneous goods and services"                           -> 12
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_ANALYTICAL_TABLES_URL = "https://www.stat.tj/en/analytical-tables/"
_FALLBACK_XLSX_URL = (
    "https://www.stat.tj/wp-content/uploads/2026/07/cpi_by_546_items_2015-en.xlsx"
)
_COUNTRY = "Tajikistan"
_SOURCE_KEY = "tj_stattj_cpi"
_BASE_PERIOD = "previous month=100"
_SHEET_NAME = "Лист1"

_DIVISION_LABELS = {
    "food on (without alcoholic beverages and tobacco products)": "01",
    "alcoholic beverages and tobacco products": "02",
    "clothing and footwear (including repairs)": "03",
    "housing and communal services": "04",
    "household items, household equipment and routine household maintenance": "05",
    "health care": "06",
    "transport": "07",
    "relationship": "08",
    "leisure, entertainment and culture": "09",
    "education": "10",
    "restaurants and hotels": "11",
    "miscellaneous goods and services": "12",
}

_MONTH_ALIASES = {
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
    "september": 9,
    "oct": 10,
    "october": 10,
    "oktovber": 10,  # 2024/2025 typo
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    "desember": 12,  # 2024/2025 typo
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _clean_label(v) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v).replace("\xa0", " ")).strip().lower()


def _discover_xlsx_url(session) -> str:
    try:
        resp = session.get(_ANALYTICAL_TABLES_URL, timeout=30)
        resp.raise_for_status()
        matches = re.findall(
            r'href="(https://www\.stat\.tj/wp-content/uploads/[^"]*cpi_by_546_items[^"]*\.xlsx)"',
            resp.text,
        )
        if matches:
            return matches[-1]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] analytical-tables discovery failed: %s", _SOURCE_KEY, exc)
    return _FALLBACK_XLSX_URL


def _build_column_dates(header_row) -> dict[int, date]:
    """Map column index -> first-of-month date, from the year/month header row."""
    col_dates: dict[int, date] = {}
    current_year: int | None = None
    for col_idx, cell in enumerate(header_row):
        if cell is None:
            continue
        if isinstance(cell, (int, float)) and 1900 < cell < 2100:
            current_year = int(cell)
            continue
        month_key = _clean_label(cell)
        month_num = _MONTH_ALIASES.get(month_key)
        if month_num is None or current_year is None:
            continue
        col_dates[col_idx] = date(current_year, month_num, 1)
    return col_dates


def fetch_tj_stattj_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    xlsx_url = _discover_xlsx_url(session)
    resp = session.get(xlsx_url, timeout=60, verify=False)
    resp.raise_for_status()

    df = pd.read_excel(
        io.BytesIO(resp.content), sheet_name=_SHEET_NAME, header=None
    )

    header_row = None
    for _, r in df.iterrows():
        # header row is the first row whose 2nd cell is a plausible year int
        if isinstance(r[1], (int, float)) and 1900 < r[1] < 2100:
            header_row = r
            break
    if header_row is None:
        logger.warning("[%s] could not locate year/month header row", _SOURCE_KEY)
        return None
    col_dates = _build_column_dates(header_row)

    found_labels: set[str] = set()
    rows = []
    for _, r in df.iterrows():
        label = _clean_label(r[0])
        coicop = _DIVISION_LABELS.get(label)
        if coicop is None:
            continue
        found_labels.add(label)
        for col_idx, obs_date in col_dates.items():
            if obs_date <= cutoff:
                continue
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
                "source_url": xlsx_url,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    missing = set(_DIVISION_LABELS) - found_labels
    if missing:
        logger.warning("[%s] division labels not found in workbook: %s", _SOURCE_KEY, missing)

    return pd.DataFrame(rows) if rows else None
