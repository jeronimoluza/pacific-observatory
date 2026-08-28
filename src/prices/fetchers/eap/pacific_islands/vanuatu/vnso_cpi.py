"""Vanuatu Bureau of Statistics (VNSO) -- quarterly Consumer Price Index.

The CPI landing page embeds "Table 2: Consumer Price Indices by Expenditure
Group" as a fully server-rendered HTML table (a Joomla "raw HTML" content
block, not a linked PDF) -- no PDF parsing needed, just BeautifulSoup on the
live page. The table appears to be updated in place each quarter at the
same fixed URL and carries the full historical series (2020-present at time
of writing) split into four location blocks: national ("Vanuatu") plus three
towns (Port Vila, Luganville, Lenakel).

All four location blocks are emitted. `subnational_area` is None for the
national series and carries the town name for the other three; it is part of
`_IDENT`, so the four locations' same-quarter/same-division values stay
distinct instead of colliding on one (date, coicop_code) key.

Base period: "1st Quarter 2000 = 100" (read from the page; not hardcoded
beyond the fallback below).

VNSO's 12 published groups map to 11 COICOP-2018 divisions + a headline
"All Groups" column (dropped -- no sanctioned headline sentinel yet, per
onboarding SKILL.md's open design question). Division 11 (restaurants &
accommodation) and 12 (insurance & financial services) are not broken out
separately and are presumed folded into "Miscellaneous" -> COICOP 13
("Personal care, social protection and miscellaneous goods and services" --
the official division of that name). NOTE: the neighbouring sinso_cpi.py
fetcher (Solomon Islands, not touched by this onboarding run) maps its own
"Miscellaneous goods and services" column to COICOP 12 instead of 13 --
that looks like the same mis-mapping this module originally had before
being corrected against data/prices/enrich/gold/coicop_leaves.txt; worth a
follow-up fix, out of scope here.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import urllib3
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

# vnso.gov.vu (*.gov.vu, Sectigo-issued) serves an incomplete chain -- the
# leaf validates fine against clients that chase AIA for the missing
# intermediate (macOS/curl do; python's certifi-only ssl context doesn't).
# Not a bot block or an expired cert -- same "NSO portal SSL certificate
# failures" class as the Mongolia/Laos entries in known_blockers.md; verify=False
# is that class's documented workaround.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_CPI_URL = (
    "https://vnso.gov.vu/index.php/en/statistics/economic-statistics/"
    "consumer-price-index"
)
_COUNTRY = "Vanuatu"
_SOURCE_KEY = "vu_vnso_cpi"
_DEFAULT_BASE_PERIOD = "1st Quarter 2000=100"
_IDENT = ["source_key", "observation_date", "coicop_code", "subnational_area"]

# Column order in "Table 2" -> COICOP-2018 division. "Miscellaneous" maps to
# 13 ("Personal care, social protection and miscellaneous goods and
# services" -- the official COICOP-2018 division of that name), which also
# absorbs the divisions VNSO doesn't break out separately (11 restaurants &
# accommodation, 12 insurance & financial services).
_COICOP_COLUMNS = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "13"]

_QUARTER_MONTH = {"1st": 1, "2nd": 4, "3rd": 7, "4th": 10}


def _parse_table(soup: BeautifulSoup) -> tuple[list[tuple], str]:
    """Returns (rows, base_period) where rows is a list of
    (subnational_area, obs_date, coicop_code, index_value)."""
    base_period = _DEFAULT_BASE_PERIOD
    base_tag = soup.select_one(".base-en")
    if base_tag and base_tag.get_text(strip=True):
        base_period = (
            base_tag.get_text(strip=True).removeprefix("Base:").strip().replace(" ", "")
        )

    table = soup.select_one("table.full-cpi-table")
    if table is None:
        return [], base_period

    current_location: str | None = None
    current_year: int | None = None
    results: list[tuple] = []

    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if (
            len(cells) == 1
            and cells[0].get("class")
            and "loc-header" in cells[0]["class"]
        ):
            label = cells[0].get_text(strip=True)
            current_location = None if label.lower() == "vanuatu" else label
            current_year = None
            continue

        if len(cells) < 13:
            continue

        year_text = cells[0].get_text(strip=True)
        if year_text:
            try:
                current_year = int(year_text)
            except ValueError:
                continue
        quarter = cells[1].get_text(strip=True)
        month = _QUARTER_MONTH.get(quarter)
        if current_year is None or month is None:
            continue

        obs_date = date(current_year, month, 1)
        values_text = [c.get_text(strip=True) for c in cells[2:14]]
        # last column (index 11, "All Groups") is the headline -- dropped.
        for coicop, raw in zip(_COICOP_COLUMNS, values_text[:11]):
            try:
                idx_val = float(raw)
            except ValueError:
                continue
            results.append((current_location, obs_date, coicop, idx_val))

    return results, base_period


def fetch_vu_vnso_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_CPI_URL, timeout=30, verify=False)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    parsed, base_period = _parse_table(soup)
    if not parsed:
        logger.warning("[%s] Could not parse Table 2 from %s", _SOURCE_KEY, _CPI_URL)
        return None

    rows = []
    for subnational_area, obs_date, coicop, idx_val in parsed:
        if obs_date <= cutoff:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "quarterly_avg",
            "country": _COUNTRY,
            "subnational_area": subnational_area,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": idx_val,
            "index_base_period": base_period,
            "source_url": _CPI_URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
