"""Eurostat household energy prices — electricity (nrg_pc_204) and gas (nrg_pc_202).

Bucket-2 regional aggregator: one shared module, one closure-generated fetch
function per (country, division) pair. Both datasets are biannual (half-yearly,
"YYYY-S1"/"YYYY-S2") JSON-stat 2.0 payloads from the Eurostat dissemination API.
Filtering the request by a single `geo=` code collapses the response to one
country's time series, so each fetch call only needs the latest half-year value.

Prices are requested in NAC (national currency) so non-eurozone countries report
in their own currency, matching `countries.yaml` rather than a harmonized EUR
figure. `tax=I_TAX` (all taxes and levies included) is the consumer-facing price.

Household consumption bands used: electricity band DC (2,500-4,999 kWh/yr), gas
band D2 (20-199 GJ/yr) — both mid-size "typical household" bands.

7 countries are absent from the gas dataset (no reported gas grid): Cyprus,
Malta, Finland, Iceland, Norway, Montenegro, Kosovo — no gas fetcher is
generated for them.
"""

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_ELEC_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_204"
)
_GAS_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_202"
)

# our_cc (ISO 3166-1 alpha-2, lowercase) -> (Eurostat geo code, countries.yaml name, currency)
_COUNTRIES = {
    "be": ("BE", "Belgium", "EUR"),
    "bg": ("BG", "Bulgaria", "BGN"),
    "cz": ("CZ", "Czech Republic", "CZK"),
    "dk": ("DK", "Denmark", "DKK"),
    "de": ("DE", "Germany", "EUR"),
    "ee": ("EE", "Estonia", "EUR"),
    "ie": ("IE", "Ireland", "EUR"),
    "gr": ("EL", "Greece", "EUR"),
    "es": ("ES", "Spain", "EUR"),
    "fr": ("FR", "France", "EUR"),
    "hr": ("HR", "Croatia", "EUR"),
    "it": ("IT", "Italy", "EUR"),
    "cy": ("CY", "Cyprus", "EUR"),
    "lv": ("LV", "Latvia", "EUR"),
    "lt": ("LT", "Lithuania", "EUR"),
    "lu": ("LU", "Luxembourg", "EUR"),
    "hu": ("HU", "Hungary", "HUF"),
    "mt": ("MT", "Malta", "EUR"),
    "nl": ("NL", "Netherlands", "EUR"),
    "at": ("AT", "Austria", "EUR"),
    "pl": ("PL", "Poland", "PLN"),
    "pt": ("PT", "Portugal", "EUR"),
    "ro": ("RO", "Romania", "RON"),
    "si": ("SI", "Slovenia", "EUR"),
    "sk": ("SK", "Slovak Republic", "EUR"),
    "fi": ("FI", "Finland", "EUR"),
    "se": ("SE", "Sweden", "SEK"),
    "is": ("IS", "Iceland", "ISK"),
    "li": ("LI", "Liechtenstein", "CHF"),
    "no": ("NO", "Norway", "NOK"),
    "gb": ("UK", "United Kingdom", "GBP"),
    "ba": ("BA", "Bosnia and Herzegovina", "BAM"),
    "me": ("ME", "Montenegro", "EUR"),
    "md": ("MD", "Moldova", "MDL"),
    "mk": ("MK", "North Macedonia", "MKD"),
    "ge": ("GE", "Georgia", "GEL"),
    "al": ("AL", "Albania", "ALL"),
    "rs": ("RS", "Serbia", "RSD"),
    "tr": ("TR", "Türkiye", "TRY"),
    "ua": ("UA", "Ukraine", "UAH"),
    "xk": ("XK", "Kosovo", "EUR"),
}

_NO_GAS = {"cy", "mt", "fi", "is", "no", "me", "xk"}

_IDENT = ["source_key", "observation_date"]


def _fetch_energy(cc: str, division: str, cutoff: date) -> pd.DataFrame | None:
    """Fetch the latest published half-year household price for one country.

    division: "electricity" (nrg_pc_204) or "gas" (nrg_pc_202).
    """
    geo, country_name, currency = _COUNTRIES[cc]
    if division == "electricity":
        url = _ELEC_URL
        params = {
            "format": "JSON",
            "lang": "EN",
            "nrg_cons": "KWH2500-4999",
            "unit": "KWH",
            "tax": "I_TAX",
            "currency": "NAC",
            "geo": geo,
        }
        unit = "kWh"
        item_name = (
            "Electricity, household band DC (2,500-4,999 kWh/yr), all taxes incl."
        )
        coicop = "04.5.1"
        source_key = f"{cc}_eurostat_electricity"
    else:
        if cc in _NO_GAS:
            return None
        url = _GAS_URL
        params = {
            "format": "JSON",
            "lang": "EN",
            "nrg_cons": "GJ20-199",
            "unit": "GJ_GCV",
            "tax": "I_TAX",
            "currency": "NAC",
            "geo": geo,
        }
        unit = "GJ"
        item_name = "Natural gas, household band D2 (20-199 GJ/yr), all taxes incl."
        coicop = "04.5.2"
        source_key = f"{cc}_eurostat_gas"

    session = get_session()
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    values = payload.get("value") or {}
    if not values:
        return None

    time_index = payload["dimension"]["time"]["category"]["index"]
    inv_time = {v: k for k, v in time_index.items()}

    latest_key = max(int(k) for k in values.keys())
    period_label = inv_time.get(latest_key)
    if not period_label or "-S" not in period_label:
        return None

    year, half = period_label.split("-S")
    month = "01" if half == "1" else "07"
    obs_date = f"{year}-{month}-01"
    if date.fromisoformat(obs_date) <= cutoff:
        return None

    price = float(values[str(latest_key)])
    if price <= 0:
        logger.warning(
            "Eurostat %s price non-positive for %s: %s — dropping", division, cc, price
        )
        return None

    row = {
        "observation_date": obs_date,
        "period_kind": "effective_from",
        "country": country_name,
        "source_key": source_key,
        "item_name": item_name,
        "price_local": price,
        "currency": currency,
        "unit": unit,
        "coicop_code": coicop,
        "effective_from": obs_date,
        "source_url": f"{url}?geo={geo}",
        "scrape_ts": get_scrape_ts(),
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return pd.DataFrame([row])


def _make_electricity_fetcher(cc: str):
    def _fn(cutoff: date) -> pd.DataFrame | None:
        return _fetch_energy(cc, "electricity", cutoff)

    _fn.__name__ = f"fetch_{cc}_eurostat_electricity"
    return _fn


def _make_gas_fetcher(cc: str):
    def _fn(cutoff: date) -> pd.DataFrame | None:
        return _fetch_energy(cc, "gas", cutoff)

    _fn.__name__ = f"fetch_{cc}_eurostat_gas"
    return _fn


for _cc in _COUNTRIES:
    globals()[f"fetch_{_cc}_eurostat_electricity"] = _make_electricity_fetcher(_cc)
    if _cc not in _NO_GAS:
        globals()[f"fetch_{_cc}_eurostat_gas"] = _make_gas_fetcher(_cc)
