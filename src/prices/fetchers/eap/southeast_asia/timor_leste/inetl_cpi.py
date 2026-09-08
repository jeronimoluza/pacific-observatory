"""INETL (National Institute of Statistics Timor-Leste) -- national CPI
time series, by COICOP-like division.

Confirmed live 2026-09-06. INETL publishes a monthly WordPress post titled
"CPI Time Series <Month> <Year>" (slug "cpi-time-series-may-2026", etc.)
under https://inetl-ip.gov.tl/category/documents-publication/consumer-
price-index-documents/. Each post embeds ONE xlsx workbook
("<Month>-<Year>-Time-Series-CPI-Series-<n>....xlsx") that re-publishes the
FULL national index history to date -- not just the latest month. The
workbook has 4 sheets (Timor-Leste, Dili, Baucau, Other); only the
national "Timor-Leste" sheet is used here.

Sheet layout (0-indexed, header=None read): row 0 holds one date per
column from column 4 onward (monthly, 2012-12-01 .. latest); rows 2..N
hold one series per row, column 0 = INETL's own code, column 1 = label.
The level-index block runs from row 2 until the first row with a blank
code (confirmed at row 50 in the 2026-09-06 pull); a second "Monthly
Change" block with the SAME code list follows further down and is never
reached because the fetcher stops at the first blank-code row.

Only whole-number codes ("1".."10", i.e. no decimal point) are kept and
zero-padded to a 2-digit COICOP division ("1" -> "01"). This covers
divisions 01-10 of COICOP-1999's 12 -- INETL's basket does not publish
11 (Restaurants and hotels) or 12 (Miscellaneous goods and services) as
separate lines at time of writing; that is a real gap in the source, not
a fetcher bug. Two special codes are dropped (no COICOP mapping):
'a' ("ALL GROUPS", the headline all-items index -- no sanctioned
all-items sentinel, same choice as zamstats_cpi.py) and '0' (appears
twice, "Tradeable" / "Non-Tradeable" -- an INETL-specific cross-cut, not
a COICOP grouping).

Base period 2018-08-16=100 (confirmed by scanning the ALL GROUPS row for
the first 100.0 value in the 2026-09-06 pull).

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled.
"""

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://inetl-ip.gov.tl/wp-json/wp/v2/posts"
_SOURCE_URL = "https://inetl-ip.gov.tl/category/documents-publication/consumer-price-index-documents/"
_COUNTRY = "Timor-Leste"
_SOURCE_KEY = "tl_inetl_cpi"
_BASE_PERIOD = "2018-08=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_SHEET = "Timor-Leste"

_XLSX_RE = re.compile(r'href="(https://inetl-ip\.gov\.tl/wp-content/uploads/[^"]*\.xlsx)"', re.I)
_DIVISION_RE = re.compile(r"^\d{1,2}$")


def _find_latest_post() -> tuple[str, str] | None:
    """Returns (content_html, slug) for the newest 'cpi-time-series-*' post."""
    try:
        resp = curl_requests.get(
            _SEARCH_URL,
            params={
                "search": "Time Series CPI",
                "per_page": 20,
                "orderby": "date",
                "order": "desc",
            },
            impersonate="chrome124",
            timeout=30,
        )
        resp.raise_for_status()
        posts = resp.json()
    except Exception:
        logger.warning("[%s] wp-json posts lookup failed", _SOURCE_KEY, exc_info=True)
        return None

    for post in posts:
        slug = post.get("slug", "")
        if not slug.startswith("cpi-time-series-"):
            continue
        content = post.get("content", {}).get("rendered", "")
        return content, slug
    return None


def _parse_level_index_block(df: pd.DataFrame) -> dict[str, list]:
    """Returns {'dates': [...], 'rows': [(code, [values...]), ...]}."""
    dates = df.iloc[0, 4:].tolist()
    rows = []
    for i in range(2, len(df)):
        code = df.iloc[i, 0]
        if pd.isna(code):
            break  # end of level-index block, before "Monthly Change" repeats it
        rows.append((str(code).strip(), df.iloc[i, 4:].tolist()))
    return {"dates": dates, "rows": rows}


def fetch_tl_inetl_cpi(cutoff: date) -> pd.DataFrame | None:
    scrape_ts = get_scrape_ts()
    found = _find_latest_post()
    if not found:
        logger.warning("[%s] could not resolve latest CPI post", _SOURCE_KEY)
        return None
    content, slug = found

    m = _XLSX_RE.search(content)
    if not m:
        logger.warning("[%s] no xlsx attachment on post %s", _SOURCE_KEY, slug)
        return None
    xlsx_url = m.group(1)

    try:
        resp = curl_requests.get(xlsx_url, impersonate="chrome124", timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.warning("[%s] xlsx download failed for %s", _SOURCE_KEY, xlsx_url, exc_info=True)
        return None

    try:
        df = pd.read_excel(BytesIO(resp.content), sheet_name=_SHEET, header=None)
    except Exception:
        logger.warning("[%s] unreadable workbook at %s", _SOURCE_KEY, xlsx_url, exc_info=True)
        return None

    block = _parse_level_index_block(df)
    dates = block["dates"]

    all_rows: list[dict] = []
    for code, values in block["rows"]:
        if not _DIVISION_RE.match(code):
            continue  # skip subdivisions (e.g. "1.1") -- division-level only
        if code == "0":
            continue  # "Tradeable"/"Non-Tradeable" -- not a COICOP division
        coicop_code = code.zfill(2)

        for d, v in zip(dates, values):
            if pd.isna(d) or pd.isna(v):
                continue
            try:
                obs_date = pd.Timestamp(d).date()
                index_value = float(v)
            except (ValueError, TypeError):
                continue
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop_code,
                "index_value": round(index_value, 4),
                "index_base_period": _BASE_PERIOD,
                "source_url": xlsx_url,
                "notes": "INETL CPI Time Series workbook, 'Timor-Leste' (national) sheet.",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            all_rows.append(row)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
