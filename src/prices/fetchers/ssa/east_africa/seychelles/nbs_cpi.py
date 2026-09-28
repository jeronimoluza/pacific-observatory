"""National Bureau of Statistics (Seychelles) -- monthly Consumer Price Index,
sub-group of items time series.

NBS (nbs.gov.sc) publishes a single cumulative XLSX workbook, "Consumer
Price Index Time Series", relinked every month under a new numeric
node-id slug and linked from the site **homepage**
(`/downloads/<id>-consumer-price-index-time-series[-<month>-<year>]/download`;
NOT the `/statistics/consumer-price-indices` or the yearly
`/downloads/38-economic-statistics/8-consumer-price-index/<id>-<year>`
listing pages -- those carry only the monthly PDF press releases, a
differently-shaped bulletin this fetcher does not parse). This fetcher
discovers the current link by taking the highest numeric node-id among
matching hrefs on the homepage -- the site's ids are monotonically
increasing per upload, confirmed by the three ids visible 2026-09-28
(1980 "1980 base", 1992 "1992 base 2", 2006 "August 2026", i.e. strictly
increasing with recency).

Verified live 2026-09-28: `curl_cffi` needs `impersonate="safari17_0"`
(chrome124/chrome120 both 403 on this host). Workbook sheet "CPI_Series"
is laid out as one row per COICOP-1999-style group (column A = label),
with monthly index values starting at column D = January 2007 and
continuing one column per month through the latest release (August 2026
at column 241 as of this pass) -- headers on row 3 (month name) / row 4
(year). This fetcher only reads the 12 top-level group rows (not their
indented sub-rows, e.g. "FISH"/"OTHER FOOD" under "FOOD AND
NON-ALCOHOLIC BEVERAGE" are dropped to avoid double-counting the parent).

COICOP: NBS publishes the legacy COICOP-1999 12-group breakdown, not the
2018 13-division split -- mapped 1:1 to codes "01".."12" per
_GROUP_TO_COICOP below (same convention as BPS Indonesia in the skill's
worked example: division 13 has no separate NBS group and is not
fabricated). "ALL ITEMS" (headline) and "NON-FOOD ITEMS" (an aggregate of
several divisions, not a COICOP group) are dropped -- no sanctioned
all-items sentinel (open design question in the skill).

analytical_role: cpi_benchmark (IndexObservation). Currency/units: none,
this is an index (base year varies by series, read from row 1's title
where stated; NBS's own base is not always restated per group so
index_base_period is left as the workbook's own header text).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import openpyxl
import pandas as pd

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://www.nbs.gov.sc/"
_SITE_ROOT = "https://www.nbs.gov.sc"
_COUNTRY = "Seychelles"
_SOURCE_KEY = "nbs_cpi_sc"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_SHEET = "CPI_Series"
_DATA_START_COL = 4  # column D, 1-indexed for openpyxl
_HEADER_ROW = 3  # month names
_YEAR_ROW = 4
_LABEL_COL = 1

_DOWNLOAD_LINK_RE = re.compile(
    r'href="(/downloads/(\d+)-consumer-price-index-time-series[^"]*/download)"',
    re.IGNORECASE,
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# NBS's own top-level group label (exact row-A text) -> COICOP-2018 code.
# Legacy COICOP-1999 12-group breakdown; no separate division 13.
_GROUP_TO_COICOP = {
    "FOOD AND NON-ALCOHOLIC BEVERAGE": "01",
    "ALCOHOLIC BEVERAGES AND TOBACCO": "02",
    "Clothing and footwear": "03",
    "Housing, water, electricity, & gas": "04",
    "Furniture & household equipment": "05",
    "Health": "06",
    "Transport": "07",
    "Communication": "08",
    "Recreation and culture": "09",
    "Education": "10",
    "Restaurants and hotels": "11",
    "Miscellaneous goods and services": "12",
}


def _discover_xlsx_url(session) -> str | None:
    resp = session.get(_LISTING_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, _LISTING_URL
        )
        return None
    matches = _DOWNLOAD_LINK_RE.findall(resp.text)
    if not matches:
        logger.warning("[%s] no download links found on %s", _SOURCE_KEY, _LISTING_URL)
        return None
    href, _node_id = max(matches, key=lambda pair: int(pair[1]))
    return _SITE_ROOT + href


def fetch_nbs_cpi_sc(cutoff: date) -> pd.DataFrame | None:
    from curl_cffi import requests as curl_requests

    session = curl_requests.Session(impersonate="safari17_0")
    xlsx_url = _discover_xlsx_url(session)
    if xlsx_url is None:
        return None

    resp = session.get(xlsx_url, timeout=60)
    if resp.status_code != 200 or not resp.content[:2] == b"PK":
        logger.warning(
            "[%s] HTTP %s / non-xlsx response from %s",
            _SOURCE_KEY,
            resp.status_code,
            xlsx_url,
        )
        return None

    wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)
    if _SHEET not in wb.sheetnames:
        logger.warning("[%s] sheet %s not found in workbook", _SOURCE_KEY, _SHEET)
        return None
    ws = wb[_SHEET]

    # Build column -> observation_date map from the month/year header rows.
    col_dates: dict[int, date] = {}
    for col in range(_DATA_START_COL, ws.max_column + 1):
        month_name = ws.cell(row=_HEADER_ROW, column=col).value
        year_val = ws.cell(row=_YEAR_ROW, column=col).value
        if not month_name or not year_val:
            continue
        month = _MONTHS.get(str(month_name).strip().lower()[:3])
        if month is None:
            continue
        try:
            col_dates[col] = date(int(year_val), month, 1)
        except (TypeError, ValueError):
            continue

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    seen_codes: set[str] = set()
    for row_idx in range(1, ws.max_row + 1):
        label = ws.cell(row=row_idx, column=_LABEL_COL).value
        if not label:
            continue
        coicop_code = _GROUP_TO_COICOP.get(str(label).strip())
        if coicop_code is None:
            continue
        # The sheet repeats each group label in later blocks (successive
        # rebasing periods share the same column layout) -- only the
        # FIRST (topmost) occurrence is the primary, full-range series;
        # later ones are sparse/zero-filled for most columns and would
        # otherwise collide with duplicate (date, coicop_code) rows.
        if coicop_code in seen_codes:
            continue
        seen_codes.add(coicop_code)
        for col, obs_date in col_dates.items():
            if obs_date <= cutoff:
                continue
            value = ws.cell(row=row_idx, column=col).value
            if value is None:
                continue
            try:
                index_value = round(float(value), 2)
            except (TypeError, ValueError):
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "subnational_area": None,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop_code,
                "index_value": index_value,
                "index_base_period": "unspecified per-group base (NBS workbook)",
                "source_url": xlsx_url,
                "notes": f"NBS group: {label}",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info("[%s] no new rows past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    logger.info(
        "[%s] %d index rows from %s (cutoff=%s)", _SOURCE_KEY, len(rows), xlsx_url, cutoff
    )
    return pd.DataFrame(rows)
