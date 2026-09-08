"""NISR (National Institute of Statistics of Rwanda) — national CPI time series.

Walks the "Price indices (CPI/PPI)" publication category on
statistics.gov.rw, finds the newest "Consumer Price Index (CPI) <Month>
<Year>" publication page, and downloads that page's ``CPI_time_series_*.xls``
attachment. The workbook's "All Rwanda" sheet holds the national (not
urban/rural-split) monthly index series, one row per COICOP division/group
(division-level "01".."12" plus a handful of food subgroups like "01.1.1"),
with one column per month back to 2009-02.

COICOP-1999-style 12-division scheme (no division 13 in this publisher's
grouping, matching BPS Indonesia and Bahrain's cpi_odp) — the all-items
headline row (coicop_code="00") is dropped per the skill's open
headline-CPI question.

TLS note: statistics.gov.rw's certificate SAN does not cover the hostname
actually served (confirmed on both apex and ``www.``) — this is a
certificate misconfiguration, not a WAF, so ``verify=False`` is used
throughout with the InsecureRequestWarning suppressed.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import requests
import urllib3

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_CATEGORY_URL = "https://www.statistics.gov.rw/statistical-publications/price-indices-cpi-ppi"
_BASE = "https://www.statistics.gov.rw"
_COUNTRY = "Rwanda"
_SOURCE_KEY = "nisr_cpi"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_HEADERS = {"User-Agent": "pacific-observatory/prices (+research)"}

_CPI_PAGE_RE = re.compile(
    r'href="(/statistical-publications/price-indices-cpi-ppi/consumer-price-index-cpi-[a-z0-9-]+)"',
    re.IGNORECASE,
)
_XLS_RE = re.compile(r'href="([^"]+CPI_time_series[^"]*\.xls)"', re.IGNORECASE)
_BASE_LABEL_RE = re.compile(r"Reference:\s*([A-Za-z]+ \d{4})=100")


def _find_latest_publication_page() -> str | None:
    resp = requests.get(_CATEGORY_URL, headers=_HEADERS, timeout=30, verify=False)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for category page", _SOURCE_KEY, resp.status_code)
        return None
    matches = _CPI_PAGE_RE.findall(resp.text)
    if not matches:
        return None
    # Pages are listed newest-first; take the first hit.
    return _BASE + matches[0]


def _find_xls_url(pub_page_url: str) -> str | None:
    resp = requests.get(pub_page_url, headers=_HEADERS, timeout=30, verify=False)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for publication page", _SOURCE_KEY, resp.status_code)
        return None
    matches = _XLS_RE.findall(resp.text)
    if not matches:
        return None
    url = matches[0]
    return url if url.startswith("http") else _BASE + url


def fetch_nisr_cpi(cutoff: date) -> pd.DataFrame | None:
    pub_page = _find_latest_publication_page()
    if not pub_page:
        logger.warning("[%s] could not locate a CPI publication page", _SOURCE_KEY)
        return None

    xls_url = _find_xls_url(pub_page)
    if not xls_url:
        logger.warning("[%s] could not locate CPI_time_series xls on %s", _SOURCE_KEY, pub_page)
        return None

    resp = requests.get(xls_url, headers=_HEADERS, timeout=60, verify=False)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d downloading %s", _SOURCE_KEY, resp.status_code, xls_url)
        return None

    xl = pd.ExcelFile(io.BytesIO(resp.content))
    df = xl.parse("All Rwanda", header=None)

    base_match = _BASE_LABEL_RE.search(str(df.iloc[2, 3]))
    index_base_period = f"{base_match.group(1)}=100" if base_match else "unknown"

    # Row 3 (0-indexed) holds the month headers starting at column 5.
    date_cols = [
        j for j in range(5, df.shape[1]) if isinstance(df.iloc[3, j], (pd.Timestamp,)) or hasattr(df.iloc[3, j], "year")
    ]

    rows: list[dict] = []
    for i in range(5, df.shape[0]):
        coicop_code = df.iloc[i, 2]
        if not isinstance(coicop_code, str) or not re.match(r"^\d{2}(\.\d+)*$", coicop_code):
            continue
        if coicop_code == "00":
            continue  # all-items headline — no sanctioned coicop_code sentinel yet
        for j in date_cols:
            val = df.iloc[i, j]
            if pd.isna(val):
                continue
            month = df.iloc[3, j]
            obs_date = date(month.year, month.month, 1)
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop_code,
                "index_value": float(val),
                "index_base_period": index_base_period,
                "source_url": pub_page,
                "notes": None,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None

    out = pd.DataFrame(rows)
    dup_count = int(out["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning("[%s] %d duplicate observation_hash rows before de-dup", _SOURCE_KEY, dup_count)
        out = out.drop_duplicates(subset="observation_hash")
    return out
