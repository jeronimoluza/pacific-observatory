"""South Africa — Stats SA Consumer Price Index (P0141), COICOP-2018 groups.

Stats SA (Statistics South Africa) publishes the CPI statistical release
"P0141" monthly at a predictable URL:
    https://www.statssa.gov.za/publications/P0141/P0141<Month><Year>.pdf
e.g. P0141July2026.pdf. No JSON/CSV/XLS feed was found (statssa.gov.za's
"Time Series Data" page links only to a generic download-by-series-code
tool, not a stable CPI file) -- the PDF is the primary machine-readable
form. `pdfplumber.extract_tables()` recovers "Table E - Consumer price
indices for all urban areas" cleanly: it is a 3-level indented table
(division / group / sub-group) where a *top-level* row has a name in
column 0 and empty strings in columns 1-2. Verified live 2026-09-01 across
2017-2026 (URL, table position, and column layout are all stable across
that span; probed January 2017, July 2018, June 2023, December 2024,
January 2025, July 2026).

Two basket eras exist in that span, both handled here:

- **Pre-2025 (Dec-2021=100 and earlier rebasings, "Communication" /
  "Recreation and culture" / "Miscellaneous goods and services" wording):
  12 top-level groups. 11 map cleanly to COICOP 2018 divisions 01-11.
  "Miscellaneous goods and services" is dropped (logged) rather than
  mapped: it is the sum of what the 2025 rebase later split into COICOP
  divisions 12 (Insurance and financial services) and 13 (Personal care
  and misc.) and cannot be disaggregated from this table.
- **From the January 2025 report (Dec-2024=100) onward**: 13 top-level
  groups, a clean 1:1 match to COICOP 2018 divisions 01-13 ("Information
  and communication" -> 08, "Recreation, sport and culture" -> 09,
  "Insurance and financial services" -> 12, "Personal care and
  miscellaneous services" -> 13, etc).

The "All items (CPI Headline)" row is intentionally dropped -- there is no
sanctioned COICOP sentinel for the all-items index in IndexObservation
(see the skill's open design question).

Each monthly PDF's Table E carries THREE index columns (year-ago month,
previous month, current/report month) -- only the current-month column
(the 7th cell of the 9-cell row: name, blank, blank, weight, idx_t-12,
idx_t-1, idx_t, %chg_mom, %chg_yoy) is emitted; the earlier two columns
will already have been emitted by their own month's report.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "South Africa"
_SOURCE_KEY = "statssa_cpi"
_LANDING_URL = "https://www.statssa.gov.za/?page_id=735&id=3"
_IDENT = ["source_key", "observation_date", "coicop_code"]

# Normalized top-level group name -> COICOP 2018 division. Covers both the
# pre-2025 (12-group) and post-2025 (13-group) basket eras; names that
# agree across eras (Food, Alcohol/tobacco, Clothing, Housing, Health,
# Transport) are listed once.
_NAME_TO_COICOP: dict[str, str] = {
    "Food and non-alcoholic beverages": "01",
    "Alcoholic beverages and tobacco": "02",
    "Clothing and footwear": "03",
    "Housing and utilities": "04",
    # pre-2025 name
    "Household contents and services": "05",
    # post-2025 name
    "Furnishings, household equipment and routine maintenance": "05",
    "Health": "06",
    "Transport": "07",
    # pre-2025 name
    "Communication": "08",
    # post-2025 name
    "Information and communication": "08",
    # pre-2025 name
    "Recreation and culture": "09",
    # post-2025 name
    "Recreation, sport and culture": "09",
    # pre-2025 name
    "Education": "10",
    # post-2025 name
    "Education services": "10",
    # pre-2025 name
    "Restaurants and hotels": "11",
    # post-2025 name
    "Restaurants and accommodation services": "11",
    "Insurance and financial services": "12",
    "Personal care and miscellaneous services": "13",
}

# Rows seen in Table E that are deliberately NOT mapped (logged, not an
# error): headline total, and the pre-2025 catch-all that spans two
# post-2025 divisions and can't be disaggregated from this table alone.
_KNOWN_UNMAPPED = {"All items (CPI Headline)", "Miscellaneous goods and services"}

_BASE_RE = re.compile(r"Index\s*\(([^)]+)=100\)")
_TRAILING_DIGIT_RE = re.compile(r"\d+$")


def _normalize_name(raw: str) -> str:
    s = raw.replace("\n", " ")
    s = re.sub(r"-\s+", "-", s)  # heal "non- alcoholic" -> "non-alcoholic"
    s = re.sub(r"\s+", " ", s).strip()
    s = _TRAILING_DIGIT_RE.sub(
        "", s
    ).strip()  # strip footnote markers, e.g. "...services1"
    return s


def _month_iter(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield date(y, m, 1)
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _parse_pdf(content: bytes, month_url: str) -> list[dict]:
    import io

    rows: list[dict] = []
    base_period = None
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Table E" not in text:
                continue
            if base_period is None:
                m = _BASE_RE.search(text)
                if m:
                    base_period = m.group(1).strip()
            for table in page.extract_tables():
                for r in table:
                    if len(r) < 7:
                        continue
                    c0, c1, c2 = r[0], r[1], r[2]
                    if c0 in (None, "") or c1 not in (None, "") or c2 not in (None, ""):
                        continue
                    name = _normalize_name(c0)
                    if name in _KNOWN_UNMAPPED or name == "Group":
                        continue
                    coicop = _NAME_TO_COICOP.get(name)
                    if coicop is None:
                        logger.warning(
                            "[%s] no COICOP mapping for group %r (%s) -- dropping row",
                            _SOURCE_KEY,
                            name,
                            month_url,
                        )
                        continue
                    try:
                        idx_val = float(str(r[6]).replace(",", "."))
                    except (TypeError, ValueError):
                        continue
                    rows.append(
                        {
                            "coicop_code": coicop,
                            "index_value": round(idx_val, 4),
                            "index_base_period": base_period or "unknown",
                            "source_url": month_url,
                        }
                    )
    return rows


def fetch_statssa_cpi(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    start = date(cutoff.year, cutoff.month, 1)
    # cutoff is itself the last collected observation_date (first-of-month);
    # start the walk the month AFTER it.
    start = date(
        start.year + (1 if start.month == 12 else 0), (start.month % 12) + 1, 1
    )
    if start > today:
        return None

    scrape_ts = get_scrape_ts()
    all_rows: list[dict] = []
    consecutive_misses = 0

    for month_date in _month_iter(start, today):
        month_name = month_date.strftime("%B")
        url = (
            "https://www.statssa.gov.za/publications/P0141/"
            f"P0141{month_name}{month_date.year}.pdf"
        )
        try:
            resp = curl_requests.get(url, impersonate="chrome124", timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.info("[%s] %s: request failed (%s)", _SOURCE_KEY, url, exc)
            consecutive_misses += 1
            if consecutive_misses >= 3:
                break
            continue
        if resp.status_code != 200:
            consecutive_misses += 1
            if consecutive_misses >= 3:
                # 3 months in a row missing means we've hit the publication
                # frontier (this month's report isn't embargo-released yet).
                break
            continue
        consecutive_misses = 0

        parsed = _parse_pdf(resp.content, url)
        if not parsed:
            logger.warning("[%s] %s: parsed 0 rows from Table E", _SOURCE_KEY, url)
            continue
        for item in parsed:
            row = {
                "observation_date": month_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": item["coicop_code"],
                "index_value": item["index_value"],
                "index_base_period": item["index_base_period"],
                "source_url": item["source_url"],
                "notes": None,
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            all_rows.append(row)

    if not all_rows:
        logger.info("[%s] nothing new after cutoff %s", _SOURCE_KEY, cutoff)
        return None

    return pd.DataFrame(all_rows)
