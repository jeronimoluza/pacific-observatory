"""AOGC Afghanistan wholesale fuel price fetcher.

Source: https://aogc.gov.af/en/pricing
API:    https://aogc.gov.af/en/pricing-data (DataTables server-side JSON)

Wholesale fuel prices from Afghanistan Oil and Gas Corporation at four
subnational pricing locations.  All prices in USD per metric ton.
"""

import logging
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_API_URL = "https://aogc.gov.af/en/pricing-data"
_SOURCE_KEY = "af_aogc"
_COUNTRY = "Afghanistan"
_CURRENCY = "USD"


def fetch_af_aogc(cutoff: date) -> pd.DataFrame | None:
    """Fetch Afghanistan wholesale fuel prices from AOGC after *cutoff*."""
    session = make_session()
    params = {"draw": "1", "start": "0", "length": "10000"}

    resp = session.get(_API_URL, params=params, timeout=60)
    resp.raise_for_status()

    payload = resp.json()
    records = payload.get("data", [])
    total = payload.get("recordsTotal", 0)

    if not records:
        logger.info("[af_aogc] No records in API response")
        return None

    if len(records) < total:
        logger.warning(
            "[af_aogc] Partial data: got %d of %d records",
            len(records),
            total,
        )

    rows: list[dict] = []
    for rec in records:
        if rec.get("is_publish") != 1:
            continue
        if rec.get("workflow_state") != "Approved":
            continue

        date_str = rec.get("date", "")
        if not date_str:
            continue
        try:
            obs_date = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            logger.warning("[af_aogc] Unparseable date: %s", date_str)
            continue
        if obs_date <= cutoff:
            continue

        price = rec.get("unit_price")
        if price is None or price == 0:
            continue

        product = rec.get("item", "").strip()
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
                "subnational_area": rec.get("price_source_type", "").strip(),
            }
        )

    if not rows:
        logger.info("[af_aogc] No new rows after cutoff %s", cutoff)
        return None

    logger.info("[af_aogc] Fetched %d new rows", len(rows))
    return pd.DataFrame(rows)
