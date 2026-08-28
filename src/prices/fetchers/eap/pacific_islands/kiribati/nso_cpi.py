"""Kiribati National Statistics Office (NSO) — Consumer Price Index.

Published quarterly at nso.gov.ki/statistics/economy/cpi/. Only the newest
release currently carries a machine-readable XLSX (older bulletins are
PDF-only); the fetcher reads that landing page for the newest linked
"*.xlsx" under the consumer-price-index download category. The XLSX's
"Quarterly Price Index" table already carries the full COICOP-division
series back to 2006, so a single fetch backfills the whole history.

Emits IndexObservation rows (analytical_role: cpi_benchmark).

Base period: 2024 Q2 = 100 (NSO normalised Q2-2024 as the new base quarter;
per the workbook's own note, older figures are re-based). 12 COICOP groups
published (division "0" is the All-Items headline and division 13 absent).
All-items headline dropped pending a sanctioned sentinel code, matching the
SINSO Solomon Islands / FSM Statistics convention.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CPI_PAGE_URL = "https://nso.gov.ki/statistics/economy/cpi/"
_COUNTRY = "Kiribati"
_SOURCE_KEY = "ki_nso_cpi"
_BASE_PERIOD = "2024 Q2=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_XLSX_RE = re.compile(
    r'href="(https://nso\.gov\.ki/download/30/consumer-price-index/[^"]*\.xlsx)"',
    re.IGNORECASE,
)
_ROMAN_TO_Q = {"I": 1, "II": 2, "III": 3, "IV": 4}
_QUARTER_START_MONTH = {1: 1, 2: 4, 3: 7, 4: 10}
_VALID_DIVISIONS = {f"{i:02d}" for i in range(1, 13)}


def _find_table_start(df: pd.DataFrame) -> int | None:
    for i in range(df.shape[0]):
        if str(df.iloc[i, 0]).strip().lower() == "quarterly price index":
            return i
    return None


def _year_by_col(row: pd.Series) -> dict[int, int]:
    years: dict[int, int] = {}
    last_year = None
    for col in row.index:
        val = row[col]
        if pd.notna(val):
            try:
                last_year = int(val)
            except (TypeError, ValueError):
                continue
        if last_year is not None:
            years[col] = last_year
    return years


def _parse_quarterly_index(
    xlsx_bytes: bytes, cutoff: date, source_url: str
) -> list[dict]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=0, header=None)

    table_start = _find_table_start(df)
    if table_start is None:
        logger.warning(
            "[%s] Could not locate 'Quarterly Price Index' table", _SOURCE_KEY
        )
        return []

    # The title row (col 0 = "Quarterly Price Index") doubles as the year
    # header row (years appear further right on the same row, one per
    # Q1 of each year); the next row carries the roman-numeral quarter
    # labels, and division data rows start right after that.
    year_row = df.iloc[table_start]
    quarter_row = df.iloc[table_start + 1]
    years = _year_by_col(year_row)

    col_periods: dict[int, date] = {}
    for col, q_label in quarter_row.items():
        if col not in years or pd.isna(q_label):
            continue
        q_num = _ROMAN_TO_Q.get(str(q_label).strip().upper())
        if q_num is None:
            continue
        col_periods[col] = date(years[col], _QUARTER_START_MONTH[q_num], 1)

    rows: list[dict] = []
    for i in range(table_start + 2, df.shape[0]):
        code_val = df.iloc[i, 0]
        if pd.isna(code_val):
            break
        code = str(code_val).strip()
        if code not in _VALID_DIVISIONS:
            continue

        for col, obs_date in col_periods.items():
            if obs_date <= cutoff:
                continue
            val = df.iloc[i, col]
            if pd.isna(val):
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "quarterly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": code,
                "index_value": float(val),
                "index_base_period": _BASE_PERIOD,
                "source_url": source_url,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return rows


def fetch_ki_nso_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_CPI_PAGE_URL, timeout=30)
    resp.raise_for_status()

    matches = _XLSX_RE.findall(resp.text)
    if not matches:
        logger.warning("[%s] No XLSX link found on %s", _SOURCE_KEY, _CPI_PAGE_URL)
        return None
    xlsx_url = matches[0]

    xlsx_resp = session.get(xlsx_url, timeout=60)
    xlsx_resp.raise_for_status()

    rows = _parse_quarterly_index(xlsx_resp.content, cutoff, xlsx_url)
    return pd.DataFrame(rows) if rows else None
