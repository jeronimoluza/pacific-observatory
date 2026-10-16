"""AOGC Afghanistan wholesale fuel price fetcher.

Source: https://aogc.gov.af/en/prices-statistics/retail-prices
API:    https://aogc.gov.af/api/v1/prices/latest (JSON)

Wholesale fuel prices from Afghanistan Oil and Gas Corporation at four
pricing locations (Kabul/Herat directorates, Hairatan/Aqina ports).  All
prices in USD per metric ton.  Despite the page title these are AOGC
wholesale rates, not pump prices.

The 2026 site rebuild retired the DataTables ``/en/pricing-data`` endpoint
(404).  The new API only serves the latest rate per (item, location) under
``data.sourceRates`` -- no history -- so the series grows one collect at a
time; ``globalRates`` are international benchmarks and are skipped.
"""

import logging
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_API_URL = "https://aogc.gov.af/api/v1/prices/latest"
_SOURCE_KEY = "af_aogc"
_COUNTRY = "Afghanistan"
_CURRENCY = "USD"


def fetch_af_aogc(cutoff: date) -> pd.DataFrame | None:
    """Fetch Afghanistan wholesale fuel prices from AOGC after *cutoff*."""
    session = make_session()
    params = {"globalLimit": "0", "sourceLimit": "10000"}

    resp = session.get(_API_URL, params=params, timeout=60)
    resp.raise_for_status()

    payload = resp.json()
    records = (payload.get("data") or {}).get("sourceRates") or []

    if not records:
        logger.info("[af_aogc] No records in API response")
        return None

    rows: list[dict] = []
    for rec in records:
        date_str = (rec.get("date") or "")[:10]
        if not date_str:
            continue
        try:
            obs_date = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            logger.warning("[af_aogc] Unparseable date: %s", date_str)
            continue
        if obs_date <= cutoff:
            continue

        price = rec.get("unitPrice")
        if price is None or price == 0:
            continue

        product = (rec.get("item") or "").strip()
        if not product:
            continue

        rows.append(
            {
                "observation_date": date_str,
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": float(price),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "ton",
                "subnational_area": (rec.get("priceSourceType") or "").strip(),
            }
        )

    if not rows:
        logger.info("[af_aogc] No new rows after cutoff %s", cutoff)
        return None

    logger.info("[af_aogc] Fetched %d new rows", len(rows))
    return pd.DataFrame(rows)
