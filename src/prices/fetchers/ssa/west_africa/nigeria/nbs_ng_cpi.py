"""Nigeria NBS "CPI and Inflation Report" — monthly Composite Consumer Price Index.

The National Bureau of Statistics publishes a monthly "CPI and Inflation
Report" XLSX (base November 2009 = 100) with five tables; this fetcher reads
**Table2** ("Composite Consumer Price Index"), the national urban+rural
series broken out into the 12-group legacy classification NBS has used since
at least 1995 (a coarser scheme than COICOP-2018's 13 divisions — division
13, insurance and financial services, is not broken out separately here; it
sits folded inside "Miscellaneous Goods & Services").

Like ``nbs_selected_food.py``, there is no stable per-month URL — each
edition is announced on the ``/elibrary`` catalog with its own numeric
document id, and the fetcher discovers the latest "CPI and Inflation Report"
edition by searching the catalog and following the highest-dated hit to its
resource link (observed pattern: ``cpi_OCT2024.xlsx``).

Verified live 2026-09-01: the elibrary catalog search for "CPI and Inflation
Report" returns 153 editions back to 1995; the newest is "CPI and Inflation
Report October 2024" (doc id 1241583, resource ``cpi_OCT2024.xlsx``, 200,
632KB) — the same ~21-month staleness already documented for
``nbs_selected_food`` (NBS's public elibrary catalog has not been updated
since 2024-11-24 despite an internal release-schedule widget listing
editions through late 2026). Not re-litigated here; see that module's
docstring for the full staleness analysis. This fetcher's discovery is
dynamic and will pick up newer editions automatically if NBS resumes
uploading.

Table2's layout, read with ``header=None``:
  - row 0: title ("Table 2 Composite Consumer Price Index (Base ...)")
  - row 1: column names (All Items, All items less Farm Produce., ...,
    Miscellaneous Goods & Services, plus trailing %-change columns)
  - row 2: weights row (col 0 literally reads " Weights")
  - row 3+: one row per month, col 0 = year (populated ONLY on the January
    row of each year, blank otherwise — forward-filled here), col 1 = month
    name.

GOTCHA confirmed live: the month-name column is **not consistently
formatted** — most rows use a 3-letter abbreviation ("Jan", "Jun") but a
visible subset use the full name ("June", "July") for no apparent reason
(e.g. rows for Jun/Jul 2004 are spelled out while every neighbouring month
that year is abbreviated). Matching on the literal string breaks silently on
those rows. Fixed by matching on the lowercased first three characters
only, which is stable for both forms in English month names.

SECOND gotcha confirmed live: the year column is populated only on each
year's January row (blank Feb-Dec, meant to be forward-filled) — except the
January row for the newest year in this edition (Jan 2024), which ships
with a BLANK year cell too, unlike every earlier January. A naive
forward-fill silently stalls on the last stated year (2023) and drops all
of 2024. Fixed by detecting the Dec->Jan month wraparound and incrementing
the year even when the cell itself is blank.

Column-to-COICOP mapping (see ``_COICOP_MAP``): the headline aggregates
("All Items", "All items less Farm Produce[.  and Energy]", "Imported
Food", "Food") are dropped — "Food" here is NBS's own narrower food-only
aggregate, not the COICOP 01 division, and "All Items" has no sanctioned
IndexObservation sentinel yet (see the skill's open design question). The
12 genuine division columns are kept and mapped 1:1, matching the pattern
already used for Guyana's fetcher (``statisticsguyana_cpi.py``) for a
legacy grouping scheme narrower than COICOP-2018.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Nigeria"
_SOURCE_KEY = "nbs_ng_cpi"
_BASE_PERIOD = "Nov2009=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_SEARCH_URL = (
    "https://nigerianstat.gov.ng/elibrary?queries%5Bsearch%5D=CPI+and+Inflation+Report"
)
_ROW_RE = re.compile(
    r"<td>(CPI and Inflation Report[^<]*)</td>.*?"
    r"<td>([A-Za-z]{3} [A-Za-z]{3} \d{1,2} \d{4})</td>.*?"
    r"elibrary/read/(\d+)",
    re.S,
)
_XLSX_RE = re.compile(r'href="([^"]+\.xlsx)"')

# Table2 column index (0-based, header=None) -> COICOP division. Columns not
# listed (0 year, 1 month, 2 All Items, 3 All items less Farm Produce, 4 All
# items less Farm Produce and Energy, 5 Imported Food, 6 Food, 19-22 %-change
# / label columns) are dropped.
_COICOP_MAP: dict[int, str] = {
    7: "01",  # Food & Non-Alcoholic Beverages
    8: "02",  # Alcoholic Beverage, Tobacco and Kola
    9: "03",  # Clothing and Footwear
    10: "04",  # Housing, Water, Electricity, Gas and Other Fuel
    11: "05",  # Furnishings & Household Equipment Maintenance
    12: "06",  # Health
    13: "07",  # Transport
    14: "08",  # Communication
    15: "09",  # Recreation & Culture
    16: "10",  # Education
    17: "11",  # Restaurant & Hotels
    18: "12",  # Miscellaneous Goods & Services
}

_MONTH_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _find_latest_edition(session) -> tuple[str, int] | None:
    try:
        r = session.get(_SEARCH_URL, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] elibrary search failed: %s", _SOURCE_KEY, exc)
        return None
    best: tuple[datetime, str, int] | None = None
    for title, date_str, doc_id in _ROW_RE.findall(r.text):
        try:
            posted = datetime.strptime(date_str, "%a %b %d %Y")
        except ValueError:
            continue
        if best is None or posted > best[0]:
            best = (posted, title.strip(), int(doc_id))
    if best is None:
        return None
    return best[1], best[2]


def _resolve_xlsx_url(session, doc_id: int) -> str | None:
    read_url = f"https://nigerianstat.gov.ng/elibrary/read/{doc_id}"
    try:
        r = session.get(read_url, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] read page fetch failed %s: %s", _SOURCE_KEY, read_url, exc)
        return None
    m = _XLSX_RE.search(r.text)
    return m.group(1) if m else None


def _rows(xlsx_bytes: bytes, source_url: str, cutoff: date) -> list[dict]:
    xl = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    if "Table2" not in xl.sheet_names:
        logger.warning(
            "[%s] no 'Table2' sheet found (have %s)", _SOURCE_KEY, xl.sheet_names
        )
        return []
    df = xl.parse("Table2", header=None)

    year = None
    prev_month_num = None
    ts = get_scrape_ts()
    out: list[dict] = []
    for _, r in df.iterrows():
        month_raw = r.get(1)
        if not isinstance(month_raw, str):
            continue
        month_num = _MONTH_NUM.get(month_raw.strip().lower()[:3])
        if month_num is None:
            continue  # title/header/weights row, or unrecognized label
        year_cell = r.get(0)
        if isinstance(year_cell, (int, float)) and not pd.isna(year_cell):
            # Publisher states the year explicitly (normal case: every
            # January row).
            year = int(year_cell)
        elif year is not None and prev_month_num == 12 and month_num == 1:
            # GOTCHA confirmed live: the January row that starts the most
            # recent year (2024 in the Oct-2024 edition) ships with a BLANK
            # year cell instead of the usual explicit label — every prior
            # January row states it. Detect the Dec->Jan wraparound and
            # infer the year increment instead of silently stalling on the
            # last stated year forever.
            year += 1
        prev_month_num = month_num
        if year is None:
            continue
        try:
            obs_date = date(year, month_num, 1)
        except ValueError:
            continue
        if obs_date <= cutoff:
            continue
        for col_idx, coicop in _COICOP_MAP.items():
            val = r.get(col_idx)
            try:
                idx_val = float(val)
            except (TypeError, ValueError):
                continue
            if pd.isna(idx_val):
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": round(idx_val, 4),
                "index_base_period": _BASE_PERIOD,
                "source_url": source_url,
                "notes": None,
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)
    return out


def fetch_nbs_ng_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    found = _find_latest_edition(session)
    if not found:
        logger.warning("[%s] no edition found on elibrary catalog", _SOURCE_KEY)
        return None
    title, doc_id = found
    xlsx_href = _resolve_xlsx_url(session, doc_id)
    if not xlsx_href:
        logger.warning(
            "[%s] no xlsx resource link on read page for doc %d", _SOURCE_KEY, doc_id
        )
        return None
    xlsx_url = (
        xlsx_href
        if xlsx_href.startswith("http")
        else f"https://nigerianstat.gov.ng{xlsx_href}"
    )
    try:
        resp = session.get(xlsx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed %s: %s", _SOURCE_KEY, xlsx_url, exc)
        return None
    rows = _rows(resp.content, xlsx_url, cutoff)
    logger.info(
        "[%s] %d rows from '%s' (doc_id=%d, cutoff=%s)",
        _SOURCE_KEY,
        len(rows),
        title,
        doc_id,
        cutoff,
    )
    return pd.DataFrame(rows) if rows else None
