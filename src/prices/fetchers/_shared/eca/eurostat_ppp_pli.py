"""Eurostat PPP price level indices by analytical category (dataset prc_ppp_ind).

Bucket-2 regional aggregator. This dataset (COICOP-1999 "analytical categories",
Eurostat's PPP/purchasing-power-parity programme) publishes annual price level
indices (PLI, EU27_2020=100) for household final consumption sub-categories,
including three that map cleanly onto COICOP-2018 divisions this shard
targets: housing/utilities (A0104 -> 04), transport (A0107 -> 07), and
restaurants & hotels (A0111 -> 11).

A PLI is a *relative* price level (how expensive a basket is vs. the EU
average), not an absolute local price -- it is emitted as IndexObservation,
the same schema used for CPI benchmarks, with `coicop_code` set to the
2-digit division. Annual cadence, one value per country per division per
year; the fetcher emits only the latest published year.

`na_item=PLI_EU27_2020` is used throughout for a consistent base across
countries and vintages. 38 ECA countries carry this dataset (Moldova,
Georgia, Ukraine and Liechtenstein are absent from prc_ppp_ind despite being
present in the sibling nrg_pc_204/202 energy datasets; Switzerland is present
here but absent there -- the two Eurostat datasets do not share one country
list). The United States and Japan are also in the raw geo list but are
out of scope for this ECA-scoped module.
"""

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PPP_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_ppp_ind"
)
_NA_ITEM = "PLI_EU27_2020"
_BASE_PERIOD = "EU27_2020=100"

# our_cc (ISO 3166-1 alpha-2, lowercase) -> (Eurostat geo code, countries.yaml name)
_COUNTRIES = {
    "be": ("BE", "Belgium"),
    "bg": ("BG", "Bulgaria"),
    "cz": ("CZ", "Czech Republic"),
    "dk": ("DK", "Denmark"),
    "de": ("DE", "Germany"),
    "ee": ("EE", "Estonia"),
    "ie": ("IE", "Ireland"),
    "gr": ("EL", "Greece"),
    "es": ("ES", "Spain"),
    "fr": ("FR", "France"),
    "hr": ("HR", "Croatia"),
    "it": ("IT", "Italy"),
    "cy": ("CY", "Cyprus"),
    "lv": ("LV", "Latvia"),
    "lt": ("LT", "Lithuania"),
    "lu": ("LU", "Luxembourg"),
    "hu": ("HU", "Hungary"),
    "mt": ("MT", "Malta"),
    "nl": ("NL", "Netherlands"),
    "at": ("AT", "Austria"),
    "pl": ("PL", "Poland"),
    "pt": ("PT", "Portugal"),
    "ro": ("RO", "Romania"),
    "si": ("SI", "Slovenia"),
    "sk": ("SK", "Slovak Republic"),
    "fi": ("FI", "Finland"),
    "se": ("SE", "Sweden"),
    "is": ("IS", "Iceland"),
    "no": ("NO", "Norway"),
    "ch": ("CH", "Switzerland"),
    "gb": ("UK", "United Kingdom"),
    "ba": ("BA", "Bosnia and Herzegovina"),
    "me": ("ME", "Montenegro"),
    "mk": ("MK", "North Macedonia"),
    "al": ("AL", "Albania"),
    "rs": ("RS", "Serbia"),
    "tr": ("TR", "Türkiye"),
    "xk": ("XK", "Kosovo"),
}

# division key -> (ppp_cat code, COICOP-2018 2-digit division, human label)
_DIVISIONS = {
    "housing": ("A0104", "04", "Housing, water, electricity, gas and other fuels"),
    "transport": ("A0107", "07", "Transport"),
    "restaurants": ("A0111", "11", "Restaurants and hotels"),
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _fetch_pli(cc: str, division_key: str, cutoff: date) -> pd.DataFrame | None:
    geo, country_name = _COUNTRIES[cc]
    ppp_cat, coicop, label = _DIVISIONS[division_key]
    source_key = f"{cc}_eurostat_ppp_{division_key}"

    session = get_session()
    resp = session.get(
        _PPP_URL,
        params={
            "format": "JSON",
            "lang": "EN",
            "na_item": _NA_ITEM,
            "ppp_cat": ppp_cat,
            "geo": geo,
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    values = payload.get("value") or {}
    if not values:
        return None

    time_index = payload["dimension"]["time"]["category"]["index"]
    inv_time = {v: k for k, v in time_index.items()}

    latest_key = max(int(k) for k in values.keys())
    year = inv_time.get(latest_key)
    if not year:
        return None

    obs_date = f"{year}-01-01"
    if date.fromisoformat(obs_date) <= cutoff:
        return None

    index_value = float(values[str(latest_key)])
    if index_value <= 0:
        logger.warning(
            "Eurostat PLI non-positive for %s/%s: %s — dropping",
            cc,
            division_key,
            index_value,
        )
        return None

    row = {
        "observation_date": obs_date,
        "period_kind": "annual_avg",
        "country": country_name,
        "source_key": source_key,
        "coicop_code": coicop,
        "index_value": index_value,
        "index_base_period": _BASE_PERIOD,
        "source_url": f"{_PPP_URL}?geo={geo}&ppp_cat={ppp_cat}",
        "notes": f"PPP price level index, {label} (COICOP {coicop})",
        "scrape_ts": get_scrape_ts(),
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return pd.DataFrame([row])


def _make_fetcher(cc: str, division_key: str):
    def _fn(cutoff: date) -> pd.DataFrame | None:
        return _fetch_pli(cc, division_key, cutoff)

    _fn.__name__ = f"fetch_{cc}_eurostat_ppp_{division_key}"
    return _fn


for _cc in _COUNTRIES:
    for _division_key in _DIVISIONS:
        globals()[f"fetch_{_cc}_eurostat_ppp_{_division_key}"] = _make_fetcher(
            _cc, _division_key
        )
