"""Palau Consumer Price Index — Graduate School USA / PITI-VITI EconMAP.

Graduate School USA's EconMAP program (pubs.pitiviti.org, "PITI-VITI") is
prepared with the Office of Planning and Statistics, Ministry of Finance,
Republic of Palau. Its annual "Palau FYxx Economic Statistics (Preliminary)"
release links a single XLSX workbook with dozens of sheets; the "Cpi" sheet
holds Table 7a "Palau Consumer Price Index (CPI), COICOP format, all items
by major groups" as a quarterly time series since 2016 Q3 — one fetch
backfills the whole history.

Emits IndexObservation rows (analytical_role: cpi_benchmark).

Base period: 2016 Q3 = 100. 12 COICOP groups published (division 13 absent,
same convention as SINSO Solomon Islands / FSM Statistics / Kiribati NSO).
All-items headline ("CPI") dropped pending a sanctioned sentinel code.

The workbook also carries Table 7b (domestic items) and Table 7c (imported
items) breakdowns by the same 12 groups — not ingested here to keep scope
to the all-items series; a future pass could add them as a domestic/
imported split, mirroring what FSM Statistics already publishes.

Staleness note: the landing-page URL is a fixed per-fiscal-year slug
("palau-fy25-economic-statistics-preliminary"). Graduate School USA
publishes a new slug each fiscal year (confirmed FY22, FY23, FY25 exist);
this fetcher targets the FY25 release specifically and will need its URL
bumped when a newer fiscal year's edition replaces it as the source of
truth — same annual-refresh limitation as any single-current-document
tariff/CPI fetcher without an archive index to crawl.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://pubs.pitiviti.org/palau-fy25-economic-statistics-preliminary"
_COUNTRY = "Palau"
_SOURCE_KEY = "pw_pitiviti_cpi"
_BASE_PERIOD = "2016 Q3=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_XLSX_RE = re.compile(
    r'href="(https://pitiviti\.org/storage/[^"]*\.xlsx)"', re.IGNORECASE
)
_QUARTER_RE = re.compile(r"^(\d{4})\s+q([1-4])$", re.IGNORECASE)
_QUARTER_START_MONTH = {1: 1, 2: 4, 3: 7, 4: 10}

_DIVISION_LABELS = [
    ("Food and non-alcoholic beverages", "01"),
    ("Alcoholic beverages, tobacco and narcotics", "02"),
    ("Clothing and footwear", "03"),
    ("Housing, water, electricity, gas and other fuels", "04"),
    ("Furnishings, household equipment and routine household maintenance", "05"),
    ("Health", "06"),
    ("Transport", "07"),
    ("Communication", "08"),
    ("Recreation and culture", "09"),
    ("Education", "10"),
    ("Restaurants and hotels", "11"),
    ("Miscellaneous goods and services", "12"),
]


def _find_table7a_start(df: pd.DataFrame) -> int | None:
    for i in range(df.shape[0]):
        val = df.iloc[i, 0]
        if isinstance(val, str) and val.strip().lower().startswith("table 7a"):
            return i
    return None


def _division_columns(header_row: pd.Series) -> dict[str, int]:
    cols: dict[str, int] = {}
    for col, val in header_row.items():
        if pd.isna(val):
            continue
        label = str(val).strip()
        for target_label, code in _DIVISION_LABELS:
            if label == target_label:
                cols[code] = col
                break
    return cols


def _parse_cpi_sheet(xlsx_bytes: bytes, cutoff: date, source_url: str) -> list[dict]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="Cpi", header=None)

    table_start = _find_table7a_start(df)
    if table_start is None:
        logger.warning("[%s] Could not locate 'Table 7a' in Cpi sheet", _SOURCE_KEY)
        return []

    header_row = df.iloc[table_start + 1]
    div_cols = _division_columns(header_row)
    if not div_cols:
        logger.warning("[%s] Could not map division columns in Cpi sheet", _SOURCE_KEY)
        return []

    rows: list[dict] = []
    # table_start + 2 is the Weights row; data starts at table_start + 3.
    for i in range(table_start + 3, df.shape[0]):
        period_label = df.iloc[i, 0]
        if not isinstance(period_label, str):
            continue
        m = _QUARTER_RE.match(period_label.strip())
        if not m:
            continue
        year, quarter_num = int(m.group(1)), int(m.group(2))

        # Rows beyond the last real release are zero-filled forecast
        # placeholders in this template — stop there.
        cpi_val = df.iloc[i, 1]
        if pd.isna(cpi_val) or float(cpi_val) == 0:
            break

        obs_date = date(year, _QUARTER_START_MONTH[quarter_num], 1)
        if obs_date <= cutoff:
            continue

        for code, col in div_cols.items():
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


def fetch_pw_pitiviti_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_PAGE_URL, timeout=30)
    resp.raise_for_status()

    matches = _XLSX_RE.findall(resp.text)
    if not matches:
        logger.warning("[%s] No XLSX link found on %s", _SOURCE_KEY, _PAGE_URL)
        return None
    xlsx_url = matches[0]

    xlsx_resp = session.get(xlsx_url, timeout=60)
    xlsx_resp.raise_for_status()

    rows = _parse_cpi_sheet(xlsx_resp.content, cutoff, xlsx_url)
    return pd.DataFrame(rows) if rows else None
