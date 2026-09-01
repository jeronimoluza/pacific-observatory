"""OMH (Office Malgache des Hydrocarbures) -- Madagascar administered pump
fuel prices.

Confirmed live 2026-09-01. The public page at
https://www.omh.mg/index.php?page=prixpompe renders an empty table filled
client-side by JS fetching a plain JSON endpoint -- no auth, no session:

    https://www.omh.mg/codes/page/prix-pompe/fetch_prices.php

Returns a flat JSON array, one row per price-schedule change (id, dates,
SC, ET, PL, GO), most-recent first, back to 2006-07-10 at fetch time (141
rows). Field meaning (confirmed against OMH's own page labels and typical
Malagasy pump-price nomenclature):
  - SC: Super Carburant (premium petrol)   -> COICOP 07.2.2
  - ET: Essence Tourisme (regular petrol)  -> COICOP 07.2.2 (discontinued
        grade -- the API sentinels it to the literal integer 1 once it's no
        longer sold, first observed at the 2026-01-05 schedule; those rows
        are dropped as no-data rather than emitted as a 1 MGA/L price)
  - PL: Petrole Lampant (kerosene)         -> COICOP 04.5.4 (matches the
        Minyak Tanah/kerosene precedent in the Pertamina ID fetcher)
  - GO: Gasoil (diesel)                    -> COICOP 07.2.2

Prices are plain-integer MGA per litre (e.g. SC=5100 means 5 100 Ar/L) --
no decimal/subunit division needed. `period_kind: effective_from` because
each row is a new administered price that holds until the next schedule
change, matching the Vanuatu/Solomon Islands tariff fetchers' convention.
"""

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = "https://www.omh.mg/codes/page/prix-pompe/fetch_prices.php"
_SOURCE_URL = "https://www.omh.mg/index.php?page=prixpompe"
_COUNTRY = "Madagascar"
_CURRENCY = "MGA"
_SOURCE_KEY = "mg_omh_fuel"
_UNIT = "L"

_FIELD_MAP = {
    "SC": ("Super Carburant (essence premium)", "07.2.2"),
    "ET": ("Essence Tourisme (essence ordinaire)", "07.2.2"),
    "GO": ("Gasoil (diesel)", "07.2.2"),
    "PL": ("Petrole lampant (kerosene)", "04.5.4"),
}

_IDENT = ["source_key", "observation_date", "item_name"]

# Sentinel value the API uses in place of a real price once a grade is
# discontinued (first seen on ET rows from the 2026-01-05 schedule onward).
_SENTINEL_NO_DATA = 1


def fetch_mg_omh_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_API_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    rows = []
    for entry in payload:
        raw_date = entry.get("dates")
        if not raw_date:
            continue
        try:
            obs_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if obs_date <= cutoff:
            continue

        for field, (item_name, coicop) in _FIELD_MAP.items():
            value = entry.get(field)
            if value is None or value == _SENTINEL_NO_DATA:
                continue
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": price,
                "currency": _CURRENCY,
                "unit": _UNIT,
                "coicop_code": coicop,
                "source_url": _SOURCE_URL,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)
