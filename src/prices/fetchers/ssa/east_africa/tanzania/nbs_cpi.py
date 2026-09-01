"""NBS (National Bureau of Statistics) Tanzania -- monthly rebased
National Consumer Price Index (NCPI), COICOP-2018 13-division breakdown.

Confirmed live 2026-09-01. NBS publishes a monthly release at
https://www.nbs.go.tz/statistics/topic/consumer-price-index-2026 with a
"CPI Summary_<MM><YYYY>.xls" download alongside the PDF release and a
neighbouring-countries-inflation PDF (neither of the latter two is used
here). GOTCHA: the topic-listing URL is year-suffixed
(`consumer-price-index-2026`) and the un-suffixed
`consumer-price-index` page carries no file downloads -- NBS rotates the
slug each January, so `_LISTING_URL` below will need a manual bump to
`consumer-price-index-2027` etc. (same maintenance pattern as
civ_dgh_fuel_tariff.py's `_KNOWN_DECISIONS`).

Each monthly .xls release conveniently republishes the FULL historical
series, one sheet per year ("2021_REBASED SERIES" .. "2026_REBASED
SERIES", verified live against the 072026 release), each sheet sharing an
identical layout: row 0 = title, row 1 = header ("S/N", "MAJOR GROUPS",
"Weights", then one column per month as a datetime), rows for S/N=1..13 =
the COICOP-2018 13 major divisions in COICOP order (S/N 1 = "Food and
Non-Alcoholic Beverages" = COICOP 01, ... S/N 13 = "Personal Care, Social
Protection and Miscellaneous Goods and Services" = COICOP 13), followed
by an "ALL ITEMS INDEX" / "INFLATION RATE" pair of summary rows (dropped
-- no sanctioned headline-index sentinel yet, per the skill's open design
question) and then an unrelated "Other Selected Groups" block (Core
Index, Non-Core Index, etc. -- dropped, not COICOP divisions). Only the
latest .xls is fetched; parsing every sheet in it yields the entire
2020-12-present series in one download.

Base period: "2017/18 weight reference; price updated to year 2020"
(index=100 at 2020 monthly average, per the sheet's own title row).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://www.nbs.go.tz/statistics/topic/consumer-price-index-2026"
_COUNTRY = "Tanzania"
_SOURCE_KEY = "tz_nbs_cpi"
_INDEX_BASE_PERIOD = "2020=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_XLS_LINK_RE = re.compile(r'href="([^"]*CPI Summary_(\d{2})(\d{4})\.xls)"', re.I)

# S/N (row order within the major-groups block) -> COICOP-2018 division.
# Confirmed against the sheet's own division names/order live 2026-09-01.
_SN_TO_COICOP = {i: f"{i:02d}" for i in range(1, 14)}


def _find_latest_xls(listing_html: str) -> str | None:
    candidates = []
    for href, mm, yyyy in _XLS_LINK_RE.findall(listing_html):
        try:
            candidates.append(((int(yyyy), int(mm)), href))
        except ValueError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def _parse_workbook(content: bytes) -> list[tuple[date, str, float]]:
    """Returns (observation_date, coicop_code, index_value) rows."""
    xl = pd.ExcelFile(io.BytesIO(content))
    out: list[tuple[date, str, float]] = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
        if df.shape[0] < 3:
            continue
        header = df.iloc[1]
        # Date columns start at index 3 (0=S/N, 1=MAJOR GROUPS, 2=Weights).
        date_cols = []
        for col in range(3, df.shape[1]):
            val = header[col]
            ts = pd.to_datetime(val, errors="coerce")
            if pd.notna(ts):
                date_cols.append((col, ts.date().replace(day=1)))
        if not date_cols:
            continue

        for row_idx in range(2, df.shape[0]):
            sn_raw = df.iat[row_idx, 0]
            try:
                sn = int(sn_raw)
            except (TypeError, ValueError):
                continue
            coicop = _SN_TO_COICOP.get(sn)
            if coicop is None:
                continue
            for col, obs_date in date_cols:
                val = df.iat[row_idx, col]
                idx_val = pd.to_numeric(val, errors="coerce")
                if pd.isna(idx_val):
                    continue
                out.append((obs_date, coicop, float(idx_val)))
            # A second "Other Selected Groups" block further down each
            # sheet also numbers its rows 1..13 (Core Index, Non Core
            # Index, ...) -- stop after the major-groups block's own
            # S/N==13 row so we never fall into it.
            if sn == 13:
                break
    return out


def fetch_tz_nbs_cpi(cutoff: date) -> pd.DataFrame | None:
    resp = curl_requests.get(_LISTING_URL, impersonate="chrome124", timeout=30)
    resp.raise_for_status()
    xls_href = _find_latest_xls(resp.text)
    if xls_href is None:
        logger.warning(
            "[%s] no CPI Summary .xls link found on %s", _SOURCE_KEY, _LISTING_URL
        )
        return None

    xls_resp = curl_requests.get(xls_href, impersonate="chrome124", timeout=30)
    xls_resp.raise_for_status()

    parsed = _parse_workbook(xls_resp.content)
    if not parsed:
        logger.warning("[%s] parsed zero rows from %s", _SOURCE_KEY, xls_href)
        return None

    scrape_ts = get_scrape_ts()
    rows = []
    for obs_date, coicop, idx_val in parsed:
        if obs_date <= cutoff:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": idx_val,
            "index_base_period": _INDEX_BASE_PERIOD,
            "source_url": xls_href,
            "notes": "NBS Tanzania rebased NCPI, COICOP-2018 13-division series.",
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None
    # De-duplicate exact (date, coicop) collisions across overlapping
    # sheet years (each release's sheet N carries a Dec-of-prior-year
    # column that also appears as sheet N-1's last column) -- keep one.
    df_out = pd.DataFrame(rows)
    df_out = df_out.drop_duplicates(
        subset=["observation_date", "coicop_code"], keep="last"
    )
    return df_out
