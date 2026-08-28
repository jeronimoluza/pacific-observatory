"""Papua New Guinea National Statistical Office (NSO) -- quarterly Consumer
Price Index (Weighted Average of 8 CPI Towns).

Discovery is two-hop because the CPI *listing* page
(statistics/economic-statistics/consumer-price-index/, redirects to
statistics/economy/consumer-price-index/) is stale -- its "latest releases"
widget only lists posts through June Quarter 2023, even though NSO keeps
publishing new quarterly XLSX/PDF releases (confirmed up to March Quarter
2025 at probe time). Those newer files are not linked from any newer blog
post; NSO appears to have kept attaching new quarterly downloads to the
June-Quarter-2023 post's own "related downloads" widget rather than
publishing new posts. So:

  1. GET the listing page, find every `/<month>-quarter-<year>` post link,
     take the most recent by (year, quarter).
  2. GET that post page and harvest every `*-final-tables*.xlsx` download
     link from its downloads widget (this is what actually surfaces the
     newest files, not the post's own nominal quarter).
  3. Pick the single most recent (year, quarter) among those hrefs --
     preferring a `-revised` filename over a plain one for the same
     quarter -- and download it.

No SSL/WAF issues here (unlike vnso.gov.vu / SINSO) -- plain `requests`
with default verification works.

Sheet "Table 3" ("CPI GROUPS, Weighted Average of 8 CPI Towns - Index
Numbers") carries both an annual summary block (skipped -- it's a subset of
the quarterly data, no new information) and the full quarterly series
grouped under bare-year marker rows. Base period "June Quarter 2012 = 100"
(confirmed from Table 13's first data column, which reads exactly 100.0).

Column order -> COICOP-2018 division (verified against the sheet's own
header row, not assumed):
  Food and non-alcoholic beverages          -> 01
  Alcoholic beverages, tobacco and betelnut -> 02
  Clothing and footwear                     -> 03
  Housing                                   -> 04
  Household equipment                       -> 05
  Transport                                 -> 07
  Communication                             -> 08
  Health                                    -> 06
  Recreation                                -> 09
  Education                                 -> 10
  Restaurants and hotels                    -> 11
  Miscellaneous                             -> 13
  All groups                                -> headline, dropped (no
                                                sanctioned sentinel yet)
Division 12 (insurance & financial services) is not broken out separately
and is presumed folded into "Miscellaneous" -> COICOP 13 ("Personal care,
social protection and miscellaneous goods and services" -- the official
division of that name), verified against
data/prices/enrich/gold/coicop_leaves.txt rather than assumed.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = (
    "https://www.nso.gov.pg/statistics/economic-statistics/consumer-price-index/"
)
_COUNTRY = "Papua New Guinea"
_SOURCE_KEY = "pg_nso_cpi"
_BASE_PERIOD = "JuneQuarter2012=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_QUARTER_MONTH = {"march": 1, "june": 4, "september": 7, "december": 10}

_COICOP_COLUMNS = [
    "01",  # Food and non-alcoholic beverages
    "02",  # Alcoholic beverages, tobacco and betelnut
    "03",  # Clothing and footwear
    "04",  # Housing
    "05",  # Household equipment
    "07",  # Transport
    "08",  # Communication
    "06",  # Health
    "09",  # Recreation
    "10",  # Education
    "11",  # Restaurants and hotels
    "13",  # Miscellaneous (COICOP 13 -- see module docstring)
    # 13th column ("All groups") is the headline -- dropped.
]

_POST_LINK_RE = re.compile(
    r'href="(https://www\.nso\.gov\.pg/statistics/economy/consumer-price-index/'
    r"(march|june|september|december)-quarter-(\d{4}))\"",
    re.IGNORECASE,
)
_XLSX_RE = re.compile(
    r'href="([^"]*/(march|june|september|december)-quarter-(\d{4})-final-tables(-revised)?\.xlsx)"',
    re.IGNORECASE,
)


def _quarter_key(month_name: str, year: str | int) -> tuple[int, int]:
    return (int(year), _QUARTER_MONTH[month_name.lower()])


def _find_latest_post_url(session) -> str | None:
    resp = session.get(_LISTING_URL, timeout=30)
    resp.raise_for_status()
    matches = _POST_LINK_RE.findall(resp.text)
    if not matches:
        return None
    best = max(matches, key=lambda m: _quarter_key(m[1], m[2]))
    return best[0]


def _find_latest_xlsx(session, post_url: str) -> str | None:
    resp = session.get(post_url, timeout=30)
    resp.raise_for_status()
    matches = _XLSX_RE.findall(resp.text)
    if not matches:
        return None
    # Prefer a "-revised" file over a plain one for the same (year, quarter).
    best_key: tuple[int, int] | None = None
    best_url: str | None = None
    best_revised = False
    for href, month_name, year, revised_suffix in matches:
        key = _quarter_key(month_name, year)
        is_revised = bool(revised_suffix)
        if (
            best_key is None
            or key > best_key
            or (key == best_key and is_revised and not best_revised)
        ):
            best_key, best_url, best_revised = key, href, is_revised
    return best_url


def _parse_table3(xls: pd.ExcelFile) -> list[tuple[date, str, float]]:
    df = xls.parse("Table 3", header=None)
    header = df.iloc[1].tolist()
    if len(header) < 14 or str(header[1]).strip() != "Food and non-alcoholic beverages":
        logger.warning("[%s] Table 3 header shape changed; aborting parse", _SOURCE_KEY)
        return []

    results: list[tuple[date, str, float]] = []
    current_year: int | None = None
    started_quarterly = False

    for _, row in df.iloc[2:].iterrows():
        label = row[0]
        rest = row[1:14]
        if isinstance(label, (int, float)) and pd.notna(label) and rest.isna().all():
            # bare-year marker row -- switches us into the quarterly block
            current_year = int(label)
            started_quarterly = True
            continue
        if not started_quarterly or current_year is None:
            continue  # still inside the annual-summary block; skip it
        month = _QUARTER_MONTH.get(str(label).strip().lower())
        if month is None:
            continue
        obs_date = date(current_year, month, 1)
        for coicop, raw in zip(_COICOP_COLUMNS, rest.tolist()[:12]):
            try:
                idx_val = float(raw)
            except (TypeError, ValueError):
                continue
            results.append((obs_date, coicop, idx_val))

    return results


def fetch_pg_nso_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    post_url = _find_latest_post_url(session)
    if not post_url:
        logger.warning(
            "[%s] Could not find a quarter post on %s", _SOURCE_KEY, _LISTING_URL
        )
        return None

    xlsx_url = _find_latest_xlsx(session, post_url)
    if not xlsx_url:
        logger.warning(
            "[%s] Could not find a final-tables xlsx on %s", _SOURCE_KEY, post_url
        )
        return None

    resp = session.get(xlsx_url, timeout=60)
    resp.raise_for_status()
    xls = pd.ExcelFile(io.BytesIO(resp.content))

    parsed = _parse_table3(xls)
    if not parsed:
        return None

    rows = []
    for obs_date, coicop, idx_val in parsed:
        if obs_date <= cutoff:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "quarterly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": idx_val,
            "index_base_period": _BASE_PERIOD,
            "source_url": xlsx_url,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
