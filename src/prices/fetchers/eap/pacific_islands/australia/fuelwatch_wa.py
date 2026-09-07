"""Western Australia FuelWatch RSS station prices.

FuelWatch is a Government of Western Australia feed of notified service-station
fuel prices. This fetcher emits a bounded daily sample: Metro North of River
prices for common household-transport fuels. The source prices are cents per
litre; emitted prices are AUD per litre.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.fuelwatch.wa.gov.au/fuelwatch/fuelWatchRSS"
_COUNTRY = "Australia"
_CURRENCY = "AUD"
_SOURCE_KEY = "au_fuelwatch_wa"
_SOURCE_URL = "https://www.fuelwatch.wa.gov.au/tools/rss"
_COICOP = "07.2.2"
_UNIT = "litre"
_REGION_ID = "25"
_REGION_NAME = "Metro North of River"
_IDENT = ["source_key", "observation_date", "product_id", "station_name", "location"]

_PRODUCTS = {
    "1": "Unleaded Petrol",
    "2": "Premium Unleaded",
    "4": "Diesel",
    "6": "98 RON",
}

_HEADERS = {
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _text(item: ET.Element, tag: str) -> str:
    value = item.findtext(tag)
    return value.strip() if value else ""


def _fetch_product(session, product_id: str, label: str, cutoff: date) -> list[dict]:
    params = {"Product": product_id, "Region": _REGION_ID, "Day": "today"}
    resp = session.get(_BASE_URL, params=params, headers=_HEADERS, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.content.lstrip(b"\xef\xbb\xbf"))
    rows: list[dict] = []
    ts = get_scrape_ts()
    for item in root.findall("./channel/item"):
        raw_date = _text(item, "date")
        try:
            obs_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if obs_date <= cutoff:
            continue

        raw_price = _text(item, "price")
        try:
            cents_per_litre = float(raw_price)
        except ValueError:
            continue
        if cents_per_litre <= 0:
            continue

        station = _text(item, "trading-name") or _text(item, "title")
        location = _text(item, "location")
        brand = _text(item, "brand")
        address = _text(item, "address")
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "daily",
            "country": _COUNTRY,
            "subnational_area": "Western Australia",
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": f"{label}, {station}",
            "price_local": round(cents_per_litre / 100.0, 4),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": resp.url,
            "notes": (
                f"FuelWatch product_id={product_id}; region={_REGION_NAME}; "
                f"brand={brand or 'na'}; location={location or 'na'}; "
                f"address={address or 'na'}; source reported {cents_per_litre:g} c/L"
            ),
            "scrape_ts": ts,
            "product_id": product_id,
            "station_name": station,
            "location": location,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("product_id")
        row.pop("station_name")
        row.pop("location")
        rows.append(row)

    logger.info("[%s] product=%s rows=%d", _SOURCE_KEY, product_id, len(rows))
    return rows


def fetch_au_fuelwatch_wa(cutoff: date) -> pd.DataFrame | None:
    session = get_session(retries=2)
    rows: list[dict] = []
    for product_id, label in _PRODUCTS.items():
        rows.extend(_fetch_product(session, product_id, label, cutoff))
    return pd.DataFrame(rows) if rows else None
