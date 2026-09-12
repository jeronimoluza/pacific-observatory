"""INSTAT (Instituti i Statistikave), Albania -- monthly CPI index by COICOP division.

INSTAT publishes NO price LEVELS. The whole of its "Prices" domain -- on the
website and in the PxWeb statistical database alike -- is index material: CPI,
HICP, producer, import, construction-cost and agricultural-product price
indices, plus a comparative price-level INDEX under purchasing power parity.
A sweep of all 944 tables in the PxWeb database (databaza.instat.gov.al:8083,
whole tree loaded 2026-09-12) returned no table of average retail prices in
lek, and neither the agriculture statistical yearbook nor the A-Z statistics
list carries one. So this source is a `cpi_benchmark` and nothing more; it is
NOT price-level coverage for Albania and must not be counted as such.

WHAT THIS READS
---------------
The CPI theme page links a family of xlsx tables. This fetcher reads the one
that carries INDEX LEVELS on the current classification:

    tab-3-ick-coicop-ver2.xlsx  --  "Indeksi i Çmimeve të Konsumit",
    COICOP Version 2, base 2025=100, monthly 2021-01 .. latest.

Its siblings are deliberately not read: tab-4 (monthly rates of change) and
tab-5 (annual rates of change) are derivatives of the same levels, tab-1/tab-2
are annual averages and annual changes, and the legacy tab-3.xlsx is the same
statistic on the OLD COICOP with a different base (Dec 2020=100, 2017-01 ..
2025-12, frozen when Version 2 took over). Splicing the legacy series onto this
one would join two classifications and two bases, so it is left alone.

LAYOUT
------
Sheet1, header=None. Row 3 is the header: col 0 "COICOP Version 2", col 1 the
Albanian group name, col 2 the basket weight, cols 3..N the months as " MM-YY"
strings (leading spaces are real and must be stripped), and the LAST column the
English title. Rows 4.. are the series: "000000" is the all-items total, then
COICOP Version 2 codes at division, group and class depth ("01.", "01.1.",
"01.1.1.", "01.1.2.2").

Only the 13 DIVISION rows are emitted -- the codes matching ^\\d{2}\\.?$ -- which
is the same "aggregate rows only" scope every other cpi_benchmark fetcher in
this repo takes (tj_stattj_cpi, bz_sib_cpi). The ~46 sub-division rows in the
same workbook are dropped; they are real and could be emitted later, but no
other CPI source in the corpus carries that depth and a lone 59-series source
would not be comparable across countries. The all-items "000000" row is also
dropped -- there is no sanctioned COICOP sentinel for a headline index (see the
onboard-price-sources open design question).

COICOP
------
`coicop_classification: publisher_labeled`: INSTAT emits its own COICOP
Version 2 codes and this fetcher only normalises them (strip the trailing dot,
zero-pad to two digits) and checks them against `_DIVISIONS`. A division row
whose normalised code is not one of the 13 is logged and DROPPED rather than
emitted with a null code.

Emits IndexObservation rows.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CPI_PAGE_URL = "https://www.instat.gov.al/en/themes/prices/consumer-price-index/"
_BASE = "https://www.instat.gov.al"
_FALLBACK_XLSX_URL = f"{_BASE}/media/45gobr53/tab-3-ick-coicop-ver2.xlsx"
_COUNTRY = "Albania"
_SOURCE_KEY = "al_instat_cpi"
_SHEET_NAME = "Sheet1"
_DEFAULT_BASE_PERIOD = "2025=100"

# COICOP Version 2 divisions, as titled by INSTAT in the workbook.
_DIVISIONS = {
    "01": "Food and non-alcoholic beverages",
    "02": "Alcoholic beverages, tobacco and narcotics",
    "03": "Clothing and footwear",
    "04": "Housing, water, electricity, gas and other fuels",
    "05": "Furnishings, household equipment and routine household maintenance",
    "06": "Health",
    "07": "Transport",
    "08": "Information and communication",
    "09": "Recreation, sport and culture",
    "10": "Education services",
    "11": "Restaurants and accommodation services",
    "12": "Insurance and financial services",
    "13": "Personal care, social protection and miscellaneous goods and services",
}

# The levels workbook, as linked from the CPI theme page. Umbraco serves it
# under a per-upload /media/<hash>/ prefix, so the filename is the stable part.
_XLSX_HREF_RE = re.compile(
    r'href="(/media/[^"]*tab-3[^"/]*ick[^"/]*coicop[^"/]*ver2[^"/]*\.xlsx)"',
    re.IGNORECASE,
)
_MONTH_RE = re.compile(r"^(\d{2})-(\d{2})$")
_DIVISION_RE = re.compile(r"^(\d{1,2})\.?$")

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _discover_xlsx_url(session) -> str:
    try:
        resp = session.get(_CPI_PAGE_URL, timeout=30)
        resp.raise_for_status()
        match = _XLSX_HREF_RE.search(resp.text)
        if match:
            return _BASE + match.group(1)
        logger.warning(
            "[%s] no tab-3 COICOP-ver2 link on %s -- using fallback URL",
            _SOURCE_KEY,
            _CPI_PAGE_URL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] CPI page discovery failed: %s", _SOURCE_KEY, exc)
    return _FALLBACK_XLSX_URL


def _column_dates(header_row) -> dict[int, date]:
    """Map column index -> first-of-month date, from the ' MM-YY' header cells."""
    col_dates: dict[int, date] = {}
    for col_idx, cell in header_row.items():
        match = _MONTH_RE.match(str(cell).strip())
        if match is None:
            continue
        month, year = int(match.group(1)), 2000 + int(match.group(2))
        col_dates[col_idx] = date(year, month, 1)
    return col_dates


def fetch_al_instat_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    xlsx_url = _discover_xlsx_url(session)
    resp = session.get(xlsx_url, timeout=60)
    resp.raise_for_status()

    df = pd.read_excel(io.BytesIO(resp.content), sheet_name=_SHEET_NAME, header=None)

    header_idx = None
    for idx, row in df.iterrows():
        if str(row[0]).strip().lower().startswith("coicop"):
            header_idx = idx
            break
    if header_idx is None:
        logger.warning("[%s] could not locate the COICOP header row", _SOURCE_KEY)
        return None

    col_dates = _column_dates(df.iloc[header_idx])
    if not col_dates:
        logger.warning("[%s] no MM-YY month columns in the header row", _SOURCE_KEY)
        return None

    base_period = _DEFAULT_BASE_PERIOD
    for cell in df.iloc[:header_idx, 0]:
        if isinstance(cell, str) and "=100" in cell:
            base_period = cell.strip()
            break

    found: set[str] = set()
    rows = []
    for _, row in df.iloc[header_idx + 1 :].iterrows():
        match = _DIVISION_RE.match(str(row[0]).strip())
        if match is None:
            continue  # total row, or a sub-division code -- out of scope
        coicop = match.group(1).zfill(2)
        if coicop not in _DIVISIONS:
            logger.warning(
                "[%s] division code %r is not a COICOP division -- dropping row",
                _SOURCE_KEY,
                str(row[0]).strip(),
            )
            continue
        found.add(coicop)
        for col_idx, obs_date in col_dates.items():
            if obs_date <= cutoff:
                continue
            value = row.get(col_idx)
            if pd.isna(value):
                continue
            try:
                index_value = float(value)
            except (TypeError, ValueError):
                logger.warning(
                    "[%s] non-numeric index value %r for %s %s -- dropping row",
                    _SOURCE_KEY,
                    value,
                    obs_date,
                    coicop,
                )
                continue
            record = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": index_value,
                "index_base_period": base_period,
                "source_url": xlsx_url,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            record["observation_hash"] = make_hash(record, _IDENT)
            rows.append(record)

    missing = set(_DIVISIONS) - found
    if missing:
        logger.warning(
            "[%s] divisions absent from the workbook: %s",
            _SOURCE_KEY,
            sorted(missing),
        )

    return pd.DataFrame(rows) if rows else None
