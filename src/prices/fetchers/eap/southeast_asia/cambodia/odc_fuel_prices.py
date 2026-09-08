"""Open Development Cambodia — daily retail fuel prices at the pump.

ODC (an NGO open-data portal, https://opendevelopmentcambodia.net/) runs a
CKAN instance at https://data.opendevelopmentcambodia.net/ that hosts a
"Retail fuel prices in Cambodia" dataset
(https://data.opendevelopmentcambodia.net/en/dataset/retail-fuel-price-at-station),
manually transcribed from Ministry of Commerce (MoC) price-notification
PDFs, one row per calendar day. Confirmed live 2026-09-06 via the CKAN
datastore API — no auth, plain GET:

    https://data.opendevelopmentcambodia.net/api/3/action/datastore_search
        ?resource_id=a5bcac01-eec8-43b4-b43d-8b4f5d98c262&limit=1000

187 rows at fetch time (2026-03-08 .. 2026-09-11 — the dataset appears to be
maintained a few days ahead of the notification's actual effective date,
harmless for our purposes since we key off the row's own im_date).

Fields: im_date (D-MM-YYYY or DD-MM-YYYY, day-first, e.g. "8-03-2026"),
regu_gas (Gasoline 92, KHR/L), diesel_gas (Gasoil 10ppm, KHR/L), moc_no
(MoC notification number), reference (source PDF filename). Both fuels are
COICOP 07.2.2 (vehicle fuel retail), matching the Ukraine/Madagascar fuel
fetcher precedent.

The moc.gov.kh site itself publishes a richer daily-commodity-price +
CPI GraphQL API (graphql.moc.gov.kh/graphql, queries publicCommodityPrice /
getPublicCpiBarChart) that was under a Cloudflare "Service Under
Maintenance" page on 2026-09-06 — worth revisiting once it's back, since it
covers non-fuel commodities this ODC mirror does not.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = (
    "https://data.opendevelopmentcambodia.net/api/3/action/datastore_search"
)
_RESOURCE_ID = "a5bcac01-eec8-43b4-b43d-8b4f5d98c262"
_SOURCE_URL = (
    "https://data.opendevelopmentcambodia.net/en/dataset/retail-fuel-price-at-station"
)
_COUNTRY = "Cambodia"
_CURRENCY = "KHR"
_SOURCE_KEY = "kh_odc_fuel"
_COICOP = "07.2.2"
_UNIT = "L"
_IDENT = ["source_key", "observation_date", "item_name"]

_FIELD_MAP = {
    "regu_gas": "Regular gasoline (Gasoline 92)",
    "diesel_gas": "Diesel (Gasoil 10ppm)",
}


def fetch_kh_odc_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(
        _API_URL, params={"resource_id": _RESOURCE_ID, "limit": 1000}, timeout=30
    )
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        logger.warning("ODC datastore_search reported failure: %s", payload)
        return None

    records = payload.get("result", {}).get("records") or []
    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    for rec in records:
        raw_date = rec.get("im_date")
        if not raw_date:
            continue
        try:
            obs_date = datetime.strptime(raw_date.strip(), "%d-%m-%Y").date()
        except ValueError:
            logger.warning("Unparseable im_date %r, skipping row", raw_date)
            continue
        if obs_date <= cutoff:
            continue

        moc_no = rec.get("moc_no") or ""
        for field, item_name in _FIELD_MAP.items():
            value = rec.get(field)
            if value is None:
                continue
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "daily",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": item_name,
                "price_local": price,
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _SOURCE_URL,
                "notes": f"MoC notification {moc_no}".strip(),
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.warning("No fuel rows extracted from ODC datastore")
        return None
    return pd.DataFrame(rows)
