"""GCC-Stat Consumer Prices — shared MENAAP fetcher, one country per callable.

The GCC Statistical Centre (GCC-Stat) publishes a harmonised monthly CPI
series by COICOP-like consumer group for all six GCC member states plus a
`Gulf Cooperation Council` regional aggregate row, via a Fusion Registry SDMX
endpoint behind its DKAN data portal (`dp.marsa.gccstat.org`). One CSV
download covers every country — no per-country querying needed — so this
module fetches the whole series once per call and filters client-side.

Dataset: GCCSTAT.ES,DF_ES_CPI,1.0 ("Consumer Prices"). Only
`UNIT == "Index"` and `FREQUENCY == "Monthly"` rows are kept — the source
also publishes annual and percentage-change series under the same dataset,
which are a different `analytical_role` (not fetched here). The 13-item
`INDICATOR` free-text column maps to 12 COICOP-2018 divisions (see
`_INDICATOR_COICOP`); the all-items headline row ("Individual consumption
expenditure of households") is dropped — no sanctioned all-items sentinel
in this pipeline yet. Division 13 does not exist separately in this
publisher's grouping (division 12 is the catch-all), matching the pattern
seen in Bahrain's own CPI portal and BPS Indonesia.

One shared module, one public ``fetch_<cc>_gccstat_cpi`` per country
(Bucket-2). Add a wrapper + YAML for a country only when it's actually
onboarded — the dataset itself already covers all six GCC states plus KSA
and UAE.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CSV_URL = (
    "https://sdmx.marsa.gccstat.org/FusionRegistry/ws/public/sdmxapi/rest/data/"
    "GCCSTAT.ES,DF_ES_CPI,1.0/all/all/?labels=name&format=csv-:-comma-true"
)
_SOURCE_KEY_SUFFIX = "gccstat_cpi"

# repo country slug (iso2, lowercase) -> the dataset's own COUNTRY label.
# Note the dataset labels the UAE "Emirates", not "United Arab Emirates".
_COUNTRIES: dict[str, tuple[str, str]] = {
    "bh": ("Bahrain", "Bahrain"),
    "kw": ("Kuwait", "Kuwait"),
    "om": ("Oman", "Oman"),
    "qa": ("Qatar", "Qatar"),
    "sa": ("Saudi Arabia", "Saudi Arabia"),
    "ae": ("United Arab Emirates", "Emirates"),
}

_INDICATOR_COICOP: dict[str, str] = {
    "Food and non-alcoholic beverages": "01",
    "Alcoholic beverages, tobacco and narcotics": "02",
    "Clothing and footwear": "03",
    "Housing, water, electricity, gas and other fuels": "04",
    "Furnishings, household equipment and routine household maintenance": "05",
    "Health": "06",
    "Transport": "07",
    "Communication": "08",
    "Recreation and culture": "09",
    "Education": "10",
    "Restaurants and hotels": "11",
    "Miscellaneous goods and services": "12",
    # "Individual consumption expenditure of households" is the all-items
    # headline — intentionally not mapped, dropped below.
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _fetch_csv(session) -> list[dict] | None:
    try:
        resp = session.get(_CSV_URL, timeout=90)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[gccstat_cpi] CSV download failed: %s", exc)
        return None
    text = resp.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _fetch_one(cc: str, cutoff: date) -> pd.DataFrame | None:
    country_name, dataset_label = _COUNTRIES[cc]
    source_key = f"{cc}_{_SOURCE_KEY_SUFFIX}"
    session = get_session()
    records = _fetch_csv(session)
    if not records:
        return None

    rows = []
    for entry in records:
        if entry.get("COUNTRY") != dataset_label:
            continue
        if entry.get("UNIT") != "Index" or entry.get("FREQUENCY") != "Monthly":
            continue
        indicator = entry.get("INDICATOR")
        coicop = _INDICATOR_COICOP.get(indicator)
        if not coicop:
            continue  # headline all-items row, or an unmapped indicator
        period = entry.get("TIME_PERIOD") or ""
        try:
            year_s, month_s = period.split("-")
            obs_date = date(int(year_s), int(month_s), 1)
        except (ValueError, AttributeError):
            continue
        if obs_date <= cutoff:
            continue
        value = entry.get("OBS_VALUE")
        if value in (None, ""):
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": country_name,
            "source_key": source_key,
            "coicop_code": coicop,
            "index_value": float(value),
            "index_base_period": "publisher-defined (see notes)",
            "source_url": "https://dp.marsa.gccstat.org/dataset/consumer-prices",
            "notes": indicator,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None


def fetch_bh_gccstat_cpi(cutoff: date) -> pd.DataFrame | None:
    return _fetch_one("bh", cutoff)


def fetch_kw_gccstat_cpi(cutoff: date) -> pd.DataFrame | None:
    return _fetch_one("kw", cutoff)


def fetch_om_gccstat_cpi(cutoff: date) -> pd.DataFrame | None:
    return _fetch_one("om", cutoff)


def fetch_qa_gccstat_cpi(cutoff: date) -> pd.DataFrame | None:
    return _fetch_one("qa", cutoff)


def fetch_sa_gccstat_cpi(cutoff: date) -> pd.DataFrame | None:
    return _fetch_one("sa", cutoff)


def fetch_ae_gccstat_cpi(cutoff: date) -> pd.DataFrame | None:
    return _fetch_one("ae", cutoff)
