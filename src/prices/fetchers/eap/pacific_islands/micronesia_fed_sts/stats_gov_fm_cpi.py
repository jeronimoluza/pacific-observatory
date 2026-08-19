"""FSM Statistics (stats.gov.fm) — Consumer Price Index, national + 4 states.

Published quarterly as a bulletin post at stats.gov.fm/consumer-price-index-*
with a linked "*_appendix.xlsx" containing the full COICOP-division index
series since 2017 for FSM nationally and each of the 4 states (Chuuk,
Kosrae, Pohnpei, Yap) in one workbook — the newest release already carries
the complete backfill, no per-quarter crawl needed.

Emits IndexObservation rows (analytical_role: cpi_benchmark).

Probe note: the "detailed <state> CPI" files under /wpfd_file/ (e.g.
2023_cpi-detailed_pohnpei) are per-state slices of this SAME index table
(INDEX / QUARTERLY INFLATION / ANNUAL INFLATION / ... sheets) — "detailed"
means finer index breakdown (domestic vs imported split, per-division),
NOT item-level average prices. There is no official_avg source here.

FSM CPI base period: 2017 Q1 = 100. 12 COICOP groups published per block
(division 13 — insurance/financial services — is absent, folded elsewhere).
All-items headline ("ALL GROUPS") is dropped pending a sanctioned sentinel
code, per the same convention as SINSO Solomon Islands.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CATEGORY_URL = "https://stats.gov.fm/category/economic/cpi/"
_COUNTRY = "Micronesia, Fed. Sts."
_SOURCE_KEY = "fm_stats_cpi"
_BASE_PERIOD = "2017 Q1=100"
_IDENT = ["source_key", "observation_date", "subnational_area", "coicop_code"]

# `subnational_area` carries the state name (Chuuk/Kosrae/Pohnpei/Yap) and is
# None for the FSM national series. It is part of _IDENT so the five blocks'
# same-quarter/same-division values stay distinct.

_DIVISION_LABELS = [
    ("Food and non-alcoholic beverages", "01"),
    ("Alcoholic beverages, tobacco and narcotics", "02"),
    ("Clothing and footwear", "03"),
    ("Housing, water, electricity and gas", "04"),
    ("Furnishings and household equipment", "05"),
    ("Health", "06"),
    ("Transport", "07"),
    ("Communication", "08"),
    ("Recreation and culture", "09"),
    ("Education", "10"),
    ("Restaurants and hotels", "11"),
    ("Miscellaneous goods and services", "12"),
]

_POST_RE = re.compile(
    r'href="(https://stats\.gov\.fm/consumer-price-index-[0-9a-z-]*)/?"', re.IGNORECASE
)
_SLUG_RE = re.compile(r"consumer-price-index-(\d{4})(?:-quarter-(\d))?", re.IGNORECASE)
_APPENDIX_RE = re.compile(
    r'href="(https://stats\.gov\.fm/download/[^"]*appendix\.xlsx)"', re.IGNORECASE
)
_QUARTER_RE = re.compile(r"^Q([1-4])-(\d{4})$", re.IGNORECASE)

_QUARTER_START_MONTH = {1: 1, 2: 4, 3: 7, 4: 10}


def _find_latest_post(session, html: str) -> str | None:
    candidates: dict[str, tuple[int, int]] = {}
    for url in _POST_RE.findall(html):
        m = _SLUG_RE.search(url)
        if not m:
            continue
        year = int(m.group(1))
        quarter = int(m.group(2)) if m.group(2) else 0
        candidates[url] = (year, quarter)
    if not candidates:
        return None
    return max(candidates, key=candidates.get)


def _state_blocks(row1: pd.Series) -> list[tuple[str | None, int]]:
    """Return [(subnational_area_or_None, block_start_col), ...] in column order."""
    blocks = []
    for col, val in row1.items():
        if pd.isna(val):
            continue
        name = str(val).strip()
        subnational = None if name.upper() == "FSM" else name.title()
        blocks.append((subnational, col))
    return sorted(blocks, key=lambda t: t[1])


def _division_columns(
    row2: pd.Series, block_start: int, block_end: int
) -> dict[str, int]:
    """Map COICOP division code -> column index within [block_start, block_end)."""
    cols: dict[str, int] = {}
    for col in range(block_start, block_end):
        val = row2.get(col)
        if pd.isna(val):
            continue
        label = str(val).strip()
        for target_label, code in _DIVISION_LABELS:
            if label == target_label:
                cols[code] = col
                break
    return cols


def _parse_index_sheet(xlsx_bytes: bytes, cutoff: date, source_url: str) -> list[dict]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="INDEX", header=None)

    row1 = df.iloc[1]
    row2 = df.iloc[2]
    blocks = _state_blocks(row1)
    if not blocks:
        logger.warning("[%s] Could not locate state blocks in INDEX sheet", _SOURCE_KEY)
        return []

    quarter_hdr_idx = None
    for i in range(df.shape[0]):
        if str(df.iloc[i, 0]).strip().lower() == "quarter":
            quarter_hdr_idx = i
            break
    if quarter_hdr_idx is None:
        logger.warning(
            "[%s] Could not locate 'Quarter' section in INDEX sheet", _SOURCE_KEY
        )
        return []

    ncols = df.shape[1]
    block_ranges = []
    for i, (subnational, start) in enumerate(blocks):
        end = blocks[i + 1][1] if i + 1 < len(blocks) else ncols
        block_ranges.append((subnational, start, end))

    rows: list[dict] = []
    for i in range(quarter_hdr_idx + 1, df.shape[0]):
        period_label = df.iloc[i, 0]
        if pd.isna(period_label):
            continue
        m = _QUARTER_RE.match(str(period_label).strip())
        if not m:
            continue
        quarter_num, year = int(m.group(1)), int(m.group(2))
        obs_date = date(year, _QUARTER_START_MONTH[quarter_num], 1)
        if obs_date <= cutoff:
            continue

        for subnational, start, end in block_ranges:
            div_cols = _division_columns(row2, start, end)
            for code, col in div_cols.items():
                val = df.iloc[i, col]
                if pd.isna(val):
                    continue
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "quarterly_avg",
                    "country": _COUNTRY,
                    "subnational_area": subnational,
                    "source_key": _SOURCE_KEY,
                    "coicop_code": code,
                    "index_value": float(val),
                    "index_base_period": _BASE_PERIOD,
                    "source_url": source_url,
                    "notes": None,
                    "scrape_ts": get_scrape_ts(),
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

    return rows


def fetch_fm_stats_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_CATEGORY_URL, timeout=30)
    resp.raise_for_status()

    post_url = _find_latest_post(session, resp.text)
    if not post_url:
        logger.warning("[%s] No CPI bulletin post found on category page", _SOURCE_KEY)
        return None

    post_resp = session.get(post_url, timeout=30)
    post_resp.raise_for_status()

    appendix_matches = _APPENDIX_RE.findall(post_resp.text)
    if not appendix_matches:
        logger.warning("[%s] No appendix .xlsx link found on %s", _SOURCE_KEY, post_url)
        return None
    appendix_url = appendix_matches[0]

    xlsx_resp = session.get(appendix_url, timeout=60)
    xlsx_resp.raise_for_status()

    rows = _parse_index_sheet(xlsx_resp.content, cutoff, appendix_url)
    return pd.DataFrame(rows) if rows else None
