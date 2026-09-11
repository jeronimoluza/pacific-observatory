"""Namibia Statistics Agency (NSA) -- monthly Consumer Price Index, food divisions.

NSA (nsa.org.na, WordPress + "Document Library Pro") publishes a monthly
"Namibia CPI <Month> <Year> Excel Tables" workbook. Sheet "Tab 6" ("Namibia
CPI by divisions (Dec.2012=100)") carries the FULL historical monthly index
series back to 2002 for every COICOP division, in one file -- there is no
need to fetch more than the single latest release to backfill the whole
history. Verified live 2026-09-11 against the August 2026 release: "Tab 6"
header row names 12 divisions incl. "FOOD AND NON-ALCOHOLIC BEVERAGES " and
"ALCOHOLIC BEVERAGES AND  TOBACCO" (note NSA's own inconsistent double
spacing in both headers -- matched by substring, not exact string).

Scope: this onboarding pass is food-only (COICOP divisions 01/02), so only
those two division columns are parsed and emitted; the other 10 published
divisions are intentionally not extracted here.

DISCOVERY: rather than hardcode a URL (release slugs are irregular --
"namibia-cpi-<month>-<year>-excel-tables" some years, "namibia-cpi-<year>
-excel-tables-<month>" others), this fetcher reads the site's Yoast
"dlp_document-sitemap.xml" (public, no auth, updated on every new release --
confirmed <lastmod> = day of the Aug-2026 upload), regex-matches document
slugs containing "cpi" + "excel-tables", parses (year, month) out of either
slug shape, and picks the newest. That document's own landing page embeds a
direct .xlsx link under wp-content/uploads/.

SHEET LOOKUP BY CONTENT, NOT NAME: NSA's own sheet-name-to-content mapping
has drifted over time (confirmed live: in the March-2023 release, the sheet
literally named "Table 14" holds a *Transport* inflation-rate table, not the
food data seen there in 2026 releases -- the workbook gained new tables
without renumbering the old ones). "Tab 6" appears stable across both the
2023 and 2026 releases sampled, but this fetcher still verifies by scanning
each sheet's header rows for "CPI by divisions" before trusting it, and logs
+ returns None rather than mis-parsing a renamed sheet.

Tested with a backdated cutoff (2002-01-01): first-run backfill emits the
full 2002-08 (Tab 6 series starts at the Dec-2012=100 rebase point but
carries pre-rebase months too) through the latest month x 2 divisions.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import openpyxl

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Namibia"
_SOURCE_KEY = "na_nsa_cpi"
_BASE_URL = "https://nsa.org.na"
_SITEMAP_URL = f"{_BASE_URL}/dlp_document-sitemap.xml"
_BASE_PERIOD = "Dec2012=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

# NSA's own header text carries inconsistent internal double-spacing; match
# on a normalised (whitespace-collapsed, uppercased) substring instead of an
# exact string.
_DIVISION_HEADERS = {
    "01": "FOOD AND NON-ALCOHOLIC BEVERAGES",
    "02": "ALCOHOLIC BEVERAGES AND TOBACCO",
}

_DOC_SLUG_RE = re.compile(
    r"<loc>(https://nsa\.org\.na/document/[^<]*cpi[^<]*excel-tables[^<]*)</loc>",
    re.IGNORECASE,
)
_XLSX_HREF_RE = re.compile(r'href="([^"]+\.xlsx)"', re.IGNORECASE)

_MONTH_NUM = {
    m.lower(): i
    for i, m in enumerate(
        [
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
        ],
        start=1,
    )
}
_MONTH_ALT = "|".join(_MONTH_NUM.keys())
# Two observed slug shapes:
#   .../namibia-cpi-2026-excel-tables-august/
#   .../namibia-cpi-august-2025-excel-tables/
_SLUG_YEAR_MONTH_RE = re.compile(
    rf"cpi-(\d{{4}})-excel-tables-({_MONTH_ALT})", re.IGNORECASE
)
_SLUG_MONTH_YEAR_RE = re.compile(
    rf"cpi-({_MONTH_ALT})-(\d{{4}})-excel-tables", re.IGNORECASE
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().upper()


def _parse_slug_period(url: str) -> tuple[int, int] | None:
    m = _SLUG_YEAR_MONTH_RE.search(url)
    if m:
        year, month_name = int(m.group(1)), m.group(2).lower()
        return year, _MONTH_NUM[month_name]
    m = _SLUG_MONTH_YEAR_RE.search(url)
    if m:
        month_name, year = m.group(1).lower(), int(m.group(2))
        return year, _MONTH_NUM[month_name]
    return None


def _find_latest_release(session) -> tuple[str, int, int] | None:
    resp = session.get(_SITEMAP_URL, timeout=30)
    resp.raise_for_status()
    candidates = _DOC_SLUG_RE.findall(resp.text)

    best: tuple[int, int, str] | None = None  # (year, month, url)
    for url in candidates:
        period = _parse_slug_period(url)
        if period is None:
            continue
        year, month = period
        if best is None or (year, month) > (best[0], best[1]):
            best = (year, month, url)
    if best is None:
        return None
    year, month, url = best
    return url, year, month


def _find_xlsx_url(doc_page_url: str, session) -> str | None:
    resp = session.get(doc_page_url, timeout=30)
    resp.raise_for_status()
    matches = _XLSX_HREF_RE.findall(resp.text)
    return matches[0] if matches else None


def _find_division_sheet(wb) -> str | None:
    for name in wb.sheetnames:
        ws = wb[name]
        for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
            for cell in row:
                if cell and "CPI BY DIVISIONS" in _norm(cell):
                    return name
    return None


def _parse_division_sheet(xlsx_bytes: bytes) -> list[tuple[date, str, float]]:
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
    sheet_name = _find_division_sheet(wb)
    if sheet_name is None:
        logger.warning(
            "[%s] No sheet matching 'CPI by divisions' found (sheets=%s)",
            _SOURCE_KEY,
            wb.sheetnames,
        )
        return []
    ws = wb[sheet_name]

    rows = list(ws.iter_rows(values_only=True))
    # Header row: column index -> COICOP code, for columns whose header
    # substring-matches one of our two food divisions.
    header_row = rows[1] if len(rows) > 1 else rows[0]
    col_to_coicop: dict[int, str] = {}
    for col_idx, val in enumerate(header_row):
        if not val:
            continue
        normed = _norm(val)
        for code, needle in _DIVISION_HEADERS.items():
            if needle in normed:
                col_to_coicop[col_idx] = code

    if not col_to_coicop:
        logger.warning(
            "[%s] Sheet '%s' matched but no food-division columns found in header",
            _SOURCE_KEY,
            sheet_name,
        )
        return []

    results: list[tuple[date, str, float]] = []
    for row in rows:
        if row is None or len(row) < 2:
            continue
        obs_dt = row[1]
        if not isinstance(obs_dt, (pd.Timestamp,)) and not hasattr(obs_dt, "year"):
            continue
        try:
            obs_date = date(obs_dt.year, obs_dt.month, 1)
        except AttributeError:
            continue
        for col_idx, coicop in col_to_coicop.items():
            if col_idx >= len(row):
                continue
            val = row[col_idx]
            try:
                idx_val = float(val)
            except (TypeError, ValueError):
                continue
            results.append((obs_date, coicop, idx_val))
    return results


def fetch_na_nsa_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    found = _find_latest_release(session)
    if found is None:
        logger.warning("[%s] No CPI excel-tables document found in sitemap", _SOURCE_KEY)
        return None
    doc_url, year, month = found

    xlsx_url = _find_xlsx_url(doc_url, session)
    if xlsx_url is None:
        logger.warning("[%s] No .xlsx link found on %s", _SOURCE_KEY, doc_url)
        return None

    xlsx_resp = session.get(xlsx_url, timeout=60)
    xlsx_resp.raise_for_status()

    parsed = _parse_division_sheet(xlsx_resp.content)
    if not parsed:
        logger.warning("[%s] Parsed zero rows from %s", _SOURCE_KEY, xlsx_url)
        return None

    ts = get_scrape_ts()
    out_rows = []
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
            "index_base_period": _BASE_PERIOD,
            "source_url": xlsx_url,
            "notes": f"NSA CPI Excel Tables, document={doc_url}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out_rows.append(row)

    return pd.DataFrame(out_rows) if out_rows else None
