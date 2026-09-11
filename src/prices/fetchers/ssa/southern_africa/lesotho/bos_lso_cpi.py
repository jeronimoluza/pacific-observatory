"""Lesotho Bureau of Statistics (BoS) — monthly Consumer Price Index.

BoS publishes a monthly CPI statistical report as a ZIP archive containing a
single PDF, at a predictable filename URL:

  https://www.bos.gov.ls/BoS_reports/Copy%20of%20Economics/CPI_<Month>_<Year>.zip

e.g. CPI_July_2026.zip, CPI_January_2025.zip. The homepage (bos.gov.ls) only
links the CURRENT month's file, and there is no archive/listing page
(directory listing 403s, publications.htm carries no CPI links) — but the
filename pattern is stable and past months' files remain live at their
predictable URL (spot-checked: every 2025 month 200s; 2026 Jan-Jul 200 except
April, which 404s — a genuine gap in BoS's own publication, not a fetcher
bug). This fetcher therefore WALKS the filename pattern month-by-month from
`_START` to the current month rather than scraping a listing page, and treats
a 404 on any single month as "not published" (skip, don't fail the whole
run).

Table 1 of each release ("Monthly Consumer Price Indices by COICOP
Divisions") carries three index-value columns per division: 13-months-ago,
last-month, and the report's own current month — but NOT a full historical
series (unlike Sierra Leone's equivalent table). So each month's release
only yields ONE new data point per division (its own current-month column);
the walk-the-filename-pattern approach is what gives this fetcher a real
backfill instead of one point per month going forward.

Base period: 2022 = 100 (yearly average), per the report's own "rebased ...
2022 = 100" text (page 2 of every checked release, 2025-2026).

No live UA/WAF gate found — bare `requests` with no headers at all returns
200 for existing files (confirmed 2026-09-11).

12 COICOP divisions published (same 01-12 layout as Sierra Leone/other SSA
NSOs — no division 13). "Overall CPI" / "Services" / "Non-durables" /
"Semi durables" / "Durables" aggregate rows are dropped (no sanctioned
all-items sentinel; the aggregate rows are not COICOP divisions).

Emits IndexObservation rows (analytical_role: cpi_benchmark).
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date

import pandas as pd
import pdfplumber
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_SOURCE_KEY = "bos_lso_cpi"
_COUNTRY = "Lesotho"
_BASE_PERIOD = "2022=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_URL_TMPL = (
    "https://www.bos.gov.ls/BoS_reports/Copy%20of%20Economics/"
    "CPI_{month}_{year}.zip"
)

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# First month verified live for this source (2026-09-11 probe).
_START = date(2025, 1, 1)

_COICOP_LABELS = {
    "01": "Food & Non-alcoholic beverages",
    "02": "Alcohol and Tobacco",
    "03": "Clothing & Footwear",
    "04": "Housing, Water, Electricity, Gas and Other Fuels",
    "05": "Furnishings, Household Equipment and Routine Maintenance of the House",
    "06": "Health",
    "07": "Transport",
    "08": "Communications",
    "09": "Recreation and culture",
    "10": "Education",
    "11": "Restaurants and Hotels",
    "12": "Miscellaneous goods and services",
}

# Matches a Table-1 division row even when the label wraps onto a second
# line before the numbers (e.g. "05. Furnishings, Household Equipment and
# Routine\nMaintenance of the House 3.32 117.90 119.40 119.71 0.3 1.5").
# Six trailing numbers = weight, idx(t-13mo), idx(t-1mo), idx(current), M%, Y%.
_DIV_ROW_RE = re.compile(
    r"(?P<code>0[1-9]|1[0-2])[.\s]+(?P<label>[A-Za-z][A-Za-z ,&\-/\n]*?)\s+"
    r"(?P<weight>\d+\.\d+)\s+(?P<idx1>\d+\.\d+)\s+(?P<idx2>\d+\.\d+)\s+"
    r"(?P<idx3>\d+\.\d+)\s+(?P<mpct>-?\d+\.\d+)\s+(?P<ypct>-?\d+\.\d+)"
)


def _months_to_try(cutoff: date, today: date) -> list[date]:
    start = max(_START, date(cutoff.year, cutoff.month, 1))
    months = []
    y, m = start.year, start.month
    while (y, m) <= (today.year, today.month):
        d = date(y, m, 1)
        if d > cutoff:
            months.append(d)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _extract_table1(pdf_bytes: bytes, report_month: date) -> list[dict]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        table_text = None
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Table 1" in text:
                table_text = text
                break
    if table_text is None:
        logger.warning("[%s] No 'Table 1' page found in %s", _SOURCE_KEY, report_month)
        return []

    start_idx = table_text.find("Table 1")
    end_idx = table_text.find("Services", start_idx)
    section = table_text[start_idx:end_idx] if end_idx > start_idx else table_text[start_idx:]

    rows = []
    for m in _DIV_ROW_RE.finditer(section):
        code = m.group("code")
        try:
            idx_current = float(m.group("idx3"))
        except ValueError:
            continue
        rows.append(
            {
                "observation_date": report_month.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": code,
                "index_value": idx_current,
                "index_base_period": _BASE_PERIOD,
                "notes": _COICOP_LABELS.get(code, ""),
            }
        )
    return rows


def fetch_bos_lso_cpi(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    candidates = _months_to_try(cutoff, today)
    if not candidates:
        return None

    session = requests.Session()
    all_rows: list[dict] = []

    for report_month in candidates:
        month_name = _MONTH_NAMES[report_month.month - 1]
        url = _URL_TMPL.format(month=month_name, year=report_month.year)
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as exc:
            logger.warning("[%s] Request failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        if resp.status_code == 404:
            logger.info("[%s] Not yet published: %s", _SOURCE_KEY, url)
            continue
        if resp.status_code != 200:
            logger.warning("[%s] Unexpected status %s for %s", _SOURCE_KEY, resp.status_code, url)
            continue

        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
            pdf_name = next(n for n in zf.namelist() if n.lower().endswith(".pdf"))
            pdf_bytes = zf.read(pdf_name)
        except Exception as exc:
            logger.warning("[%s] Could not read zip/pdf from %s: %s", _SOURCE_KEY, url, exc)
            continue

        rows = _extract_table1(pdf_bytes, report_month)
        for row in rows:
            row["source_url"] = url
            row["scrape_ts"] = get_scrape_ts()
            row["observation_hash"] = None
            row["observation_hash"] = make_hash(row, _IDENT)
        all_rows.extend(rows)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
