"""Myanmar Central Statistical Organization (CSO) -- Consumer Price Index.

The CSO "Monthly Publication / Price Analysis" page
(`/MonthlyPublication/PriceAnalysis`) links a downloadable XLSX for table
3.1 "Consumer Price Index (Union) and Rate of Inflation"
(`/Content/pdf/PriceAnalysis/p3.1MA02.xlsx`), Base 2012=100. Confirmed
machine-readable 2026-09-06 -- a "page1" print-formatted sheet plus a
cleaner "data" pivot sheet, both covering the same window.

**STALE SOURCE, flagged loudly**: despite the page being labelled a
"Monthly Publication", the XLSX's own `Last-Modified` header is
2022-12-16 and the data inside stops at June 2022 (13 months from June
2021) -- this file has not been refreshed in ~3.75 years as of this
onboarding pass (2026-09-06), even though CSO continues to publish the
surrounding HTML page. This fetcher is idempotent against that: once the
one-time historical window is ingested, every subsequent run correctly
returns `None` (nothing newer than cutoff) rather than silently
re-emitting the same 13 rows. Re-check every few months in case CSO
resumes updates -- this is a "silent truncation" candidate (flat output
looks like a healthy no-new-data response, not a broken fetcher), so the
staleness must be understood at onboarding time, not discovered later.

Only `Food_Index` (COICOP 01) is emitted. The headline `CPI` column is
dropped per the onboarding skill's open design question (no sanctioned
all-items sentinel yet). `Non_Food_Index` is ALSO dropped -- unlike
vnso_cpi.py's narrow "Miscellaneous" catch-all (COICOP 13), CSO's
Non-Food residual spans nearly every other division (housing, transport,
communication, education, clothing...) with no single COICOP code that
honestly describes it; mapping it to one division would be a worse
distortion than dropping it.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.csostat.gov.mm/Content/pdf/PriceAnalysis/p3.1MA02.xlsx"
_COUNTRY = "Myanmar"
_SOURCE_KEY = "mm_csostat_cpi"
_COICOP = "01"
_BASE_PERIOD = "2012=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3,
    "april": 4, "may": 5, "june": 6, "july": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
}


def _parse_food_index(xlsx_bytes) -> list[tuple[date, float]]:
    df = pd.read_excel(xlsx_bytes, sheet_name="page1", header=None)
    out: list[tuple[date, float]] = []
    current_year: int | None = None

    for _, row in df.iterrows():
        label = str(row[0]).strip() if pd.notna(row[0]) else ""
        food_val = row[2] if len(row) > 2 else None

        if label.isdigit() and len(label) == 4 and pd.isna(food_val):
            current_year = int(label)
            continue

        month = _MONTHS.get(label.lower())
        if month is None or current_year is None or pd.isna(food_val):
            continue
        try:
            val = float(food_val)
        except (TypeError, ValueError):
            continue
        out.append((date(current_year, month, 1), val))

    return out


def fetch_mm_csostat_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    import io

    parsed = _parse_food_index(io.BytesIO(resp.content))
    if not parsed:
        logger.warning("[%s] No Food_Index rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    rows = []
    for obs_date, idx_val in parsed:
        if obs_date <= cutoff:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "index_value": idx_val,
            "index_base_period": _BASE_PERIOD,
            "source_url": _URL,
            "notes": (
                "CSO Food_Index sub-series of the Union CPI. Source file "
                "last modified 2022-12-16 and not observed to update since "
                "-- see fetcher module docstring."
            ),
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
