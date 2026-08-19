"""Fiji Bureau of Statistics (FBoS) -- monthly Consumer Price Index.

The prices landing page (`_LISTING_URL`) lists monthly CPI release posts
newest-first, each titled "CONSUMER PRICE INDEX – <Month> <Year>"; the
fetcher finds the most recent one by (year, month) rather than trusting DOM
order, then downloads its single linked PDF and parses "Table 3: CONSUMER
PRICE INDEX: NATIONAL (BASE: AVERAGE 12 MONTHS 2019 = 100.0)" -- a clean,
text-extractable table (pdfplumber `extract_text()` returns real rows, no
OCR needed).

Only checked for Fiji publishing *both* a CPI index and a separate retail-
price-level series (which would need two manifests per onboarding doctrine)
-- it does not. The prices page covers CPI, Producer Price Index, Building
Material Price Index, and International Merchandise Trade Indexes; all four
are index series (cpi_benchmark / not-yet-onboarded index roles), none are
price-level PriceObservation data. One manifest is correct here.

Table 3 columns (verified against the sheet's own header row):
  All Items                                          -> headline, dropped
  Food and Non-alcoholic Beverages                   -> 01
  Alcoholic Beverages, Tobacco and Narcotics         -> 02
  Clothing and Footwear                              -> 03
  Housing, Water, Elec., Gas and Other Fuels         -> 04
  Furnishings, Hhld Equip. & Routine Hhld Maint.     -> 05
  Health                                             -> 06
  Transport                                          -> 07
  Communication                                      -> 08
  Recreation & Culture                               -> 09
  Education                                          -> 10
  Restaurants & Hotels                               -> 11
  Miscellaneous Goods & Services                     -> 13
Division 12 (insurance & financial services) is not broken out separately
and is presumed folded into "Miscellaneous" -> COICOP 13 ("Personal care,
social protection and miscellaneous goods and services" -- the official
division of that name), verified against
data/prices/enrich/gold/coicop_leaves.txt rather than assumed.

Only monthly rows are emitted (period_kind=monthly_avg). Table 3 also
carries an annual-average summary block above the monthly rows; it is
redundant with the monthly data (and its irregular column count for the
2019 base year -- no inflation-rate cell -- makes it more parsing risk than
it's worth), so it is skipped entirely.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://www.statsfiji.gov.fj/statistics/economic-statistics/prices/"
_COUNTRY = "Fiji"
_SOURCE_KEY = "fj_statsfiji_cpi"
_BASE_PERIOD = "Average12Months2019=100.0"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_MONTH_NUM = {
    "january": 1,
    "february": 2,
    "feruary": 2,  # typo confirmed in the July 2026 release's Table 3 (2026 rows)
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

_COICOP_COLUMNS = [
    "01",  # Food and Non-alcoholic Beverages
    "02",  # Alcoholic Beverages, Tobacco and Narcotics
    "03",  # Clothing and Footwear
    "04",  # Housing, Water, Elec., Gas and Other Fuels
    "05",  # Furnishings, Hhld Equip. & Routine Hhld Maint.
    "06",  # Health
    "07",  # Transport
    "08",  # Communication
    "09",  # Recreation & Culture
    "10",  # Education
    "11",  # Restaurants & Hotels
    "13",  # Miscellaneous Goods & Services (COICOP 13 -- see module docstring)
]

_POST_LINK_RE = re.compile(
    r'href="(https://www\.statsfiji\.gov\.fj/consumer-price-index-'
    r"([a-z]+)-(\d{4})/)\"",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"-?\d+\.\d+")


def _find_latest_post_url(session) -> str | None:
    resp = session.get(_LISTING_URL, timeout=30)
    resp.raise_for_status()
    matches = [
        (href, month.lower(), int(year))
        for href, month, year in _POST_LINK_RE.findall(resp.text)
        if month.lower() in _MONTH_NUM
    ]
    if not matches:
        return None
    best = max(matches, key=lambda m: (m[2], _MONTH_NUM[m[1]]))
    return best[0]


def _find_pdf_url(session, post_url: str) -> str | None:
    resp = session.get(post_url, timeout=30)
    resp.raise_for_status()
    m = re.search(r'href="([^"]*\.pdf)"', resp.text, re.IGNORECASE)
    return m.group(1) if m else None


def _parse_table3(text: str) -> list[tuple[date, str, float]]:
    # The plain "Table 3" heading also appears earlier, in the release's
    # cover-page list of attached tables ("Table 3: 2019 Base national
    # consumer price index") -- anchor on the real table's specific header
    # pairing instead of the first "Table 3" match.
    start_m = re.search(r"Table\s*3\s*\n\s*CONSUMER PRICE INDEX:\s*NATIONAL", text)
    if not start_m:
        return []
    end_m = re.search(r"Table\s*4\b", text[start_m.end() :])
    table_text = (
        text[start_m.end() : start_m.end() + end_m.start()]
        if end_m
        else text[start_m.end() :]
    )

    current_year: int | None = None
    results: list[tuple[date, str, float]] = []

    for line in table_text.splitlines():
        tokens = line.strip().split()
        if not tokens:
            continue
        if tokens[0].isdigit() and len(tokens[0]) == 4:
            current_year = int(tokens[0])
            tokens = tokens[1:]
        if not tokens or current_year is None:
            continue
        month = _MONTH_NUM.get(tokens[0].lower())
        if month is None:
            continue  # not a monthly row (annual/"Weight" row etc.) -- skip
        numbers = [float(t) for t in tokens[1:] if _NUM_RE.fullmatch(t)]
        if len(numbers) < len(_COICOP_COLUMNS):
            continue
        # last N numbers are [All Items, 12 divisions]; drop the leading
        # inflation-rate cell (if present) by always reading from the end.
        division_values = numbers[-len(_COICOP_COLUMNS) :]
        obs_date = date(current_year, month, 1)
        for coicop, val in zip(_COICOP_COLUMNS, division_values):
            results.append((obs_date, coicop, val))

    return results


def fetch_fj_statsfiji_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    post_url = _find_latest_post_url(session)
    if not post_url:
        logger.warning(
            "[%s] Could not find a CPI release post on %s", _SOURCE_KEY, _LISTING_URL
        )
        return None

    pdf_url = _find_pdf_url(session, post_url)
    if not pdf_url:
        logger.warning("[%s] Could not find a PDF link on %s", _SOURCE_KEY, post_url)
        return None

    resp = session.get(pdf_url, timeout=60)
    resp.raise_for_status()
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    parsed = _parse_table3(text)
    if not parsed:
        logger.warning("[%s] No Table 3 rows parsed from %s", _SOURCE_KEY, pdf_url)
        return None

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
            "index_base_period": _BASE_PERIOD,
            "source_url": pdf_url,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
