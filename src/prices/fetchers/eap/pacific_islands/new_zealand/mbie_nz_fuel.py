"""New Zealand — MBIE weekly retail fuel price monitoring.

The Ministry of Business, Innovation & Employment (MBIE) publishes a plain,
keyless CSV of its weekly retail-fuel-price monitoring series, going back to
2004:

  https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv

Verified live 2026-09-06: 35,010 data rows, long/tidy format (columns Week,
Date, Fuel, Variable, Value, Unit, Status), through week 2026w35
(2026-08-28), mostly "Final" with the most recent few weeks "Provisional".
Three retail fuels are tracked (Diesel, Regular Petrol, Premium Petrol 95R);
several rows carry Fuel="NA" for series-wide inputs (Dubai crude price,
NZD/USD exchange rate) which this fetcher does not emit.

This fetcher keeps only the `Variable == "Adjusted retail price"` rows per
fuel -- MBIE's own estimate of the actual retail pump price after taxes and
importer margin, which is what a consumer pays. `Value` is in NZD cents per
litre (c/L); converted to NZD/L (divide by 100) to match the rest of the
pipeline's per-unit convention.

Single COICOP class (vehicle fuel) -> COICOP 07.2.2.0 leaf, narrow source,
short-circuits the classifier.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from io import StringIO

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "New Zealand"
_CURRENCY = "NZD"
_SOURCE_KEY = "mbie_nz_fuel"
_SOURCE_URL = (
    "https://www.mbie.govt.nz/assets/Data-Files/Energy/"
    "Weekly-fuel-price-monitoring/weekly-table.csv"
)
_UNIT = "L"
_VARIABLE = "Adjusted retail price"
# COICOP leaves: 07.2.2.1 Diesel, 07.2.2.2 Petrol (both grades).
_FUEL_COICOP = {
    "Diesel": "07.2.2.1",
    "Regular Petrol": "07.2.2.2",
    "Premium Petrol 95R": "07.2.2.2",
}
_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_mbie_nz_fuel(cutoff: date) -> pd.DataFrame | None:
    resp = curl_requests.get(_SOURCE_URL, impersonate="chrome124", timeout=60)
    resp.raise_for_status()

    df = pd.read_csv(StringIO(resp.text))
    df = df[(df["Variable"] == _VARIABLE) & (df["Fuel"].isin(_FUEL_COICOP))]
    if df.empty:
        logger.warning("[%s] no '%s' rows found in CSV", _SOURCE_KEY, _VARIABLE)
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []

    for _, r in df.iterrows():
        try:
            obs_date = datetime.strptime(str(r["Date"]).strip(), "%d/%m/%Y").date()
        except ValueError:
            continue
        if obs_date <= cutoff:
            continue
        try:
            cents_per_l = float(r["Value"])
        except (TypeError, ValueError):
            continue

        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _FUEL_COICOP[r["Fuel"]],
            "item_name": f"{r['Fuel']}, adjusted retail price",
            "price_local": round(cents_per_l / 100.0, 6),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _SOURCE_URL,
            "notes": (
                f"MBIE weekly fuel price monitoring, week {r['Week']}, "
                f"status={r['Status']}."
            ),
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.info(
            "[%s] all observation dates <= cutoff %s -- nothing new",
            _SOURCE_KEY,
            cutoff,
        )
        return None

    return pd.DataFrame(rows)
