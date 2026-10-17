"""WFP Afghanistan retail fuel prices from the HDX food-prices dataset.

Source: https://data.humdata.org/dataset/wfp-food-prices-for-afghanistan
File:   wfp_food_prices_afg.csv (WFP VAM market monitoring, refreshed monthly)

WFP enumerators record the retail price consumers pay per litre in each
monitored market (one market per province since 2020, plus legacy city
markets). Only ``Fuel (diesel)`` is published for Afghanistan. Rows are
monthly and dated the 15th; they are normalised to the first of the month.
Each market is kept as its own row and the national value is their robust
median (see ``station_aggregate`` in the YAML).
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_CSV_URL = (
    "https://data.humdata.org/dataset/a246cbac-42d5-47b2-ba75-ac66f69e83de/"
    "resource/03e6ce5d-03a2-4e60-8d04-afa39c5972f4/download/wfp_food_prices_afg.csv"
)
_SOURCE_KEY = "af_wfp_monthly"
_COUNTRY = "Afghanistan"
_COMMODITY = "Fuel (diesel)"


def fetch_af_wfp(cutoff: date) -> pd.DataFrame | None:
    """Fetch WFP monthly retail fuel prices per market after *cutoff*."""
    resp = make_session().get(_CSV_URL, timeout=120)
    resp.raise_for_status()

    # Row 2 of every HDX WFP file is an HXL tag row (#date, #adm1+name, ...).
    raw = pd.read_csv(io.BytesIO(resp.content), skiprows=[1])
    src = raw[
        raw["commodity"].eq(_COMMODITY)
        & raw["pricetype"].eq("Retail")
        & raw["unit"].eq("L")
        & ~raw["priceflag"].astype(str).str.contains("forecast")
    ].copy()
    if src.empty:
        logger.warning("[af_wfp] No retail diesel rows in %s", _CSV_URL)
        return None

    obs = pd.to_datetime(src["date"], errors="coerce").dt.to_period("M")
    src["observation_date"] = obs.dt.to_timestamp().dt.strftime("%Y-%m-%d")
    src["price_local"] = pd.to_numeric(src["price"], errors="coerce")
    src = src[
        obs.notna()
        & (src["observation_date"] > cutoff.isoformat())
        & (src["price_local"] > 0)
    ]
    if src.empty:
        logger.info("[af_wfp] No new rows after cutoff %s", cutoff)
        return None

    out = pd.DataFrame(
        {
            "observation_date": src["observation_date"],
            "country": _COUNTRY,
            "fuel_product": src["commodity"],
            "price_local": src["price_local"],
            "currency": src["currency"],
            "source_key": _SOURCE_KEY,
            "unit": "L",
            "subnational_area": src["admin1"].astype(str).str.strip(),
            "city": src["market"].astype(str).str.strip(),
            "station": src["market"].astype(str).str.strip(),
        }
    )
    out = (
        out.drop_duplicates(subset=["observation_date", "fuel_product", "station"])
        .sort_values(["observation_date", "fuel_product", "station"])
        .reset_index(drop=True)
    )
    logger.info("[af_wfp] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
