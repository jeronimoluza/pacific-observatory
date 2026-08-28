"""Maldives Essential Commodities Price Index (ECPI), Male' — National Bureau of Statistics.

The National Bureau of Statistics (statisticsmaldives.gov.mv) publishes a
monthly "Essential Commodities Price Index" for Male' as a WordPress post at
/ecpi-<month>-<year>/, linking a "Tables" XLSX. Maldives had zero official
government price/index source before this (only a handful of small
e-commerce sites under sar/south_asia/maldives/). Re-verified live
2026-08-07: /ecpi-july-2026/ -> 200, links
ECPI-July-2026-Tables-Male.xlsx (uploaded to /2026/08/, i.e. this month) —
genuinely current, not a stale archive page. The single sheet
("Summary (Male')") is a wide COICOP_2016-coded index table running
Nov 2022 - Jul 2026 (base Nov 2022=100) for TOTAL CONSUMPTION EXPENDITURE
(00), FOOD AND BEVERAGES (01) with full 01.1.x/01.2.x subclass detail, GAS
AND OTHER FUEL (04), and PERSONAL CARE PRODUCTS (13) — this is a narrow
"essential commodities" basket, not the full CPI, so its division coverage
is genuinely limited to 00/01/04/13, not a sampling artifact. A second
table ("Table 2: Month-on-Month Inflation Rate") follows immediately below
in the same sheet and is explicitly excluded — inflation rate is a
different metric from an index level and mixing them would corrupt
index_value.

Because each month's XLSX already carries the full cumulative time series
back to Nov 2022 (not just that month), this fetcher only needs to locate
the single most recent resolving month page (probing backward, tolerating
gaps -- e.g. /ecpi-may-2026/ 404s while April and June both resolve) and
melt its one sheet to long form, rather than walking every month.

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled — NSO's own COICOP_2016 codes are
used directly (converted to COICOP-2018 dotted notation, e.g. '011' ->
'01.1', '0111' -> '01.1.1').
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Maldives"
_SOURCE_KEY = "mv_ecpi_male"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_BASE_PERIOD = "Nov 2022=100"
_MAX_MONTHS_BACK = 8
_MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
_TABLES_XLSX_RE = re.compile(r'href="([^"]*Tables-Male\.xlsx)"', re.IGNORECASE)


def _candidate_pages(today: date) -> list[tuple[str, str]]:
    out = []
    y, m = today.year, today.month
    for _ in range(_MAX_MONTHS_BACK):
        month_name = _MONTHS[m - 1]
        out.append(
            (
                f"https://statisticsmaldives.gov.mv/ecpi-{month_name}-{y}/",
                f"{month_name}-{y}",
            )
        )
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


def _find_latest_xlsx(session) -> str | None:
    for page_url, _label in _candidate_pages(date.today()):
        try:
            r = session.get(page_url, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[%s] page probe failed %s: %s", _SOURCE_KEY, page_url, exc)
            continue
        if r.status_code != 200:
            continue
        m = _TABLES_XLSX_RE.search(r.text)
        if not m:
            continue
        href = m.group(1)
        return (
            href
            if href.startswith("http")
            else f"https://statisticsmaldives.gov.mv{href}"
        )
    return None


def _coicop_2018(code_2016: str) -> str | None:
    code_2016 = str(code_2016).strip()
    if not code_2016 or not code_2016.isdigit():
        return None
    if code_2016 == "00":
        return None  # all-items headline has no sanctioned COICOP sentinel yet
    parts = [code_2016[0:2], code_2016[2:3], code_2016[3:4]]
    parts = [p for p in parts if p]
    return ".".join(parts)


def _rows_from_xlsx(xlsx_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=0, header=None)
    # Row 1 (0-based) is the real header: COICOP_2016, Description, <dates...>
    header = df.iloc[1].tolist()
    date_cols = []
    for i, h in enumerate(header):
        if i < 2:
            continue
        ts = pd.to_datetime(h, errors="coerce")
        if pd.notna(ts):
            date_cols.append((i, ts.date()))
    if not date_cols:
        return []
    # Table 1 body runs from row 2 until the next "Table" title row.
    body = df.iloc[2:]
    ts = get_scrape_ts()
    out: list[dict] = []
    for _, row in body.iterrows():
        code_raw = row.iloc[0]
        if pd.isna(code_raw):
            break  # blank separator row -> end of Table 1
        if isinstance(row.iloc[1], str) and row.iloc[1].startswith("Table"):
            break
        coicop = _coicop_2018(code_raw)
        if coicop is None:
            continue
        for col_idx, obs_date in date_cols:
            if obs_date <= cutoff:
                continue
            val = row.iloc[col_idx]
            if pd.isna(val):
                continue
            try:
                index_value = float(val)
            except (TypeError, ValueError):
                continue
            r = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": round(index_value, 4),
                "index_base_period": _BASE_PERIOD,
                "source_url": url,
                "notes": f"Essential Commodities Price Index, Male'; description={row.iloc[1]}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            r["observation_hash"] = make_hash(r, _IDENT)
            out.append(r)
    return out


def fetch_mv_ecpi_male(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    xlsx_url = _find_latest_xlsx(session)
    if not xlsx_url:
        logger.warning("[%s] no ECPI page resolved within lookback window", _SOURCE_KEY)
        return None
    try:
        resp = session.get(xlsx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed: %s", _SOURCE_KEY, exc)
        return None
    rows = _rows_from_xlsx(resp.content, xlsx_url, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
