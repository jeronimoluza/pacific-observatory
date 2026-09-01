"""Uganda Bureau of Statistics (UBOS) -- monthly Consumer Price Index.

UBOS publishes a monthly CPI news post at ubos.org (WordPress) with a
"CPI Excel Tables" attachment carrying the full index-level time series.
Rather than hardcode a URL, this fetcher discovers the latest release live
via the site's WordPress REST API:

1. GET /wp-json/wp/v2/posts?search=Consumer+Price+Index&per_page=10&
   orderby=date&order=desc -- returns post title/link/date for the most
   recent matching posts. Titles follow "Consumer Price Index <Month>
   <Year>" (e.g. "Consumer Price Index August 2026"); pick the newest by
   (year, month) parsed from the title, skipping older naming variants
   ("CPI Publication <Month> <Year>") that predate the current template.
2. GET that post's own page -- its rendered HTML embeds a direct link to
   "..._CPI_Excel_Tables_<Month>_<Year>.xlsx" under
   wp-content/uploads/statistics/, no auth required.
3. Parse the "Division " sheet (openpyxl; note the trailing space UBOS
   ships in the sheet name) with pandas, header=None. Layout verified live
   2026-09-01 against the August 2026 release: row 0 holds column headers
   -- "National Weights" in column index 2, then one date per column from
   index 3 onward (monthly, back to base period July 2017=100). Rows 1-13
   (column 0 = division number 1..13) are the index-LEVEL block -- UBOS's
   13 divisions map 1:1, in order, to the COICOP-2018 13 divisions
   (01 Food ... 13 Personal Care/Social Protection/Misc), so no manual
   remap is needed, unlike Malawi's NSO ("Miscellaneous" -> 13) or
   Vanuatu's VNSO. Row 14 ("Grand Total") is the headline all-items index;
   dropped per the open design question (no sanctioned headline sentinel
   in IndexObservation yet). Two further stacked blocks below row 14
   ("Annual % Change" from row ~20, "Monthly % Change" from row ~35) repeat
   the same 13 divisions as growth RATES, not index levels -- out of scope
   for IndexObservation and not parsed.

TLS note: www.ubos.org serves a leaf cert (`*.ubos.org`, Sectigo) without
the intermediate in the handshake -- resolves fine in curl/macOS but fails
python's certifi-only chain validation ("unable to get local issuer
certificate"). Same class of TLS quirk as vnso_cpi.py / ura_electricity_tariff.py
/ statsdiv_cpi.py in this repo; `verify=False` is the documented workaround.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_WP_API = "https://www.ubos.org/wp-json/wp/v2/posts"
_COUNTRY = "Uganda"
_SOURCE_KEY = "uga_ubos_cpi"
_DEFAULT_BASE_PERIOD = "Jul2017=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_XLSX_RE = re.compile(
    r'href="(https?://www\.ubos\.org/wp-content/uploads/statistics/'
    r'[^"]*?CPI_Excel_Tables[^"]*?\.xlsx)"',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(
    r"^Consumer Price Index\s+([A-Za-z]+)\s+(\d{4})\s*$", re.IGNORECASE
)

_MONTH_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# Division number (col 0 of the "Division " sheet, rows 1-13) -> COICOP-2018.
# UBOS's 13 divisions are already the COICOP-2018 13 divisions, in order.
_DIVISION_TO_COICOP = {i: f"{i:02d}" for i in range(1, 14)}


def _find_latest_post(posts: list[dict]) -> tuple[str, int, int] | None:
    best: tuple[int, int, str] | None = None  # (year, month, link)
    for p in posts:
        title = re.sub(r"&#\d+;", " ", p.get("title", {}).get("rendered", "")).strip()
        m = _TITLE_RE.match(title)
        if not m:
            continue
        month = _MONTH_NUM.get(m.group(1).lower())
        if month is None:
            continue
        year = int(m.group(2))
        link = p.get("link")
        if not link:
            continue
        if best is None or (year, month) > (best[0], best[1]):
            best = (year, month, link)
    if best is None:
        return None
    year, month, link = best
    return link, year, month


def _find_xlsx_url(html: str) -> str | None:
    matches = _XLSX_RE.findall(html)
    return matches[0] if matches else None


def _parse_division_sheet(xlsx_bytes: bytes) -> list[tuple[date, str, float]]:
    xl = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    sheet_name = next((s for s in xl.sheet_names if "division" in s.lower()), None)
    if sheet_name is None:
        logger.warning(
            "[%s] No 'Division' sheet found (sheets=%s)", _SOURCE_KEY, xl.sheet_names
        )
        return []
    df = xl.parse(sheet_name, header=None)

    header = df.iloc[0]
    date_cols: dict[int, date] = {}
    for col_idx in range(3, df.shape[1]):
        val = header.iloc[col_idx]
        ts = pd.to_datetime(val, errors="coerce")
        if pd.notna(ts):
            date_cols[col_idx] = ts.date().replace(day=1)

    results: list[tuple[date, str, float]] = []
    for row_idx in range(1, 14):
        div_num = df.iloc[row_idx, 0]
        try:
            div_num = int(div_num)
        except (TypeError, ValueError):
            continue
        coicop = _DIVISION_TO_COICOP.get(div_num)
        if coicop is None:
            continue
        for col_idx, obs_date in date_cols.items():
            val = df.iloc[row_idx, col_idx]
            try:
                idx_val = float(val)
            except (TypeError, ValueError):
                continue
            results.append((obs_date, coicop, idx_val))
    return results


def fetch_uga_ubos_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    resp = session.get(
        _WP_API,
        params={
            "search": "Consumer Price Index",
            "per_page": 10,
            "orderby": "date",
            "order": "desc",
        },
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    posts = resp.json()
    found = _find_latest_post(posts)
    if found is None:
        logger.warning(
            "[%s] No 'Consumer Price Index <Month> <Year>' post found", _SOURCE_KEY
        )
        return None
    post_link, year, month = found

    post_resp = session.get(post_link, timeout=30, verify=False)
    post_resp.raise_for_status()
    xlsx_url = _find_xlsx_url(post_resp.text)
    if xlsx_url is None:
        logger.warning(
            "[%s] No CPI_Excel_Tables xlsx link found on %s", _SOURCE_KEY, post_link
        )
        return None

    xlsx_resp = session.get(xlsx_url, timeout=60, verify=False)
    xlsx_resp.raise_for_status()

    parsed = _parse_division_sheet(xlsx_resp.content)
    if not parsed:
        logger.warning("[%s] Parsed zero rows from %s", _SOURCE_KEY, xlsx_url)
        return None

    ts = get_scrape_ts()
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
            "index_base_period": _DEFAULT_BASE_PERIOD,
            "source_url": xlsx_url,
            "notes": f"UBOS CPI Excel Tables, post={post_link}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
