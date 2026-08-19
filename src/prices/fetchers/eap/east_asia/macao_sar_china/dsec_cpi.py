"""DSEC Time Series Database -- Consumer Price Index (CPI), Macao SAR.

Macao's Statistics and Census Service (DSEC) exposes a legacy ASMX web
service (TimeSeriesDatabase.asmx) that also answers plain HTTP GET with a
querystring (no auth, no API key). The Composite CPI groups its basket into
11 divisions (not the COICOP-2018 13) with sequential indicator IDs
6004-6014, confirmed via getIndicatorByID:

  6004 Food and non-alcoholic beverages    -> COICOP 01
  6005 Alcoholic beverages and tobacco     -> COICOP 02
  6006 Clothing and footwear               -> COICOP 03
  6007 Housing and fuels                   -> COICOP 04
  6008 Household furnishings and services  -> COICOP 05
  6009 Health                              -> COICOP 06
  6010 Transport                           -> COICOP 07
  6011 Information & Communication         -> COICOP 08
  6012 Recreation, Sport & Culture         -> COICOP 09
  6013 Education                           -> COICOP 10
  6014 Miscellaneous goods and services     -> COICOP 12

There is no separate "Restaurants and hotels" division in Macao's CPI
grouping (verified: getIndicatorID search on "Restaurants" / "Hotels" /
"Dining" returns no Composite-CPI hit) -- COICOP 11 and the remainder of 13
are NOT covered by this fetcher. Indicator 6003 (Overall/All-items
headline) is intentionally NOT emitted: IndexObservation requires a
coicop_code and there is no sanctioned sentinel for headline CPI yet (see
singstat_cpi.py for the same convention).

Base period is 7/2023-6/2024=100. Monthly data available back to 1998.
getIndicatorLatestNValues(iLatestNRecords=400) returns full available
history in one call per indicator (confirmed: 342 records for indicator
6004, back to Jan/1998) -- the endpoint self-caps at whatever history
exists, so a generous N is safe and does not error.

Emits IndexObservation rows.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from xml.etree import ElementTree

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.dsec.gov.mo/TimeSeriesDatabase.asmx/getIndicatorLatestNValues"
_SOURCE_URL = "https://www.dsec.gov.mo/en-US/Statistic?id=501"
_COUNTRY = "Macao SAR, China"
_SOURCE_KEY = "mo_dsec_cpi"
_BASE_PERIOD = "7/2023-6/2024=100"
_NS = "{http://www.dsec.gov.mo/}"
_MAX_RECORDS = 400  # comfortably exceeds 1998-present monthly history (~340 records)

_DIVISION_MAP = {
    6004: "01",
    6005: "02",
    6006: "03",
    6007: "04",
    6008: "05",
    6009: "06",
    6010: "07",
    6011: "08",
    6012: "09",
    6013: "10",
    6014: "12",
}
_IDENT = ["source_key", "observation_date", "coicop_code"]
_PERIOD_RE = re.compile(r"^([A-Za-z]{3})/(\d{4})$")


def _parse_period(ref_period: str) -> date | None:
    m = _PERIOD_RE.match(ref_period.strip())
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(2)} {m.group(1)}", "%Y %b").date()
    except ValueError:
        return None


def fetch_mo_dsec_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    rows: list[dict] = []

    for indicator_id, coicop in _DIVISION_MAP.items():
        resp = session.get(
            _BASE_URL,
            params={
                "iIndicatorID": indicator_id,
                "vLanguageType": "English",
                "vFunctionType": "VAL",
                "vDataPeriodType": "Monthly",
                "iLatestNRecords": _MAX_RECORDS,
            },
            timeout=60,
        )
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        status = root.findtext(f"{_NS}StatusCode")
        if status != "0":
            logger.warning(
                "[%s] Non-zero StatusCode %s for indicator %s -- skipping",
                _SOURCE_KEY,
                status,
                indicator_id,
            )
            continue

        for node in root.iterfind(f"{_NS}IndicatorData/{_NS}DSECIndicatorWSData"):
            ref_period = node.findtext(f"{_NS}ReferencePeriod") or ""
            obs_date = _parse_period(ref_period)
            if obs_date is None or obs_date <= cutoff:
                continue
            raw_value = node.findtext(f"{_NS}IndicatorValue")
            if raw_value in (None, ""):
                continue
            try:
                idx = float(raw_value)
            except ValueError:
                continue

            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": idx,
                "index_base_period": _BASE_PERIOD,
                "source_url": _SOURCE_URL,
                "notes": "",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
