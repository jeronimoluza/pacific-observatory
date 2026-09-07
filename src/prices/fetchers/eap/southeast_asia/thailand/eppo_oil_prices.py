"""EPPO Thailand oil retail prices from the public WordPress JSON endpoint."""

from __future__ import annotations

import json
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices"
_COUNTRY = "Thailand"
_CURRENCY = "THB"
_SOURCE_KEY = "th_eppo_oil_prices"
_SOURCE_URL = "https://www.eppo.go.th/data-energy-statistic/energy-price-th/"
_COICOP = "07.2.2"
_UNIT = "litre"
_IDENT = ["source_key", "observation_date", "item_name"]

_BRANDS = {
    "ptt": "PTT",
    "bcp": "BCP",
    "shell": "Shell",
    "caltex": "Caltex",
    "irpc": "IRPC",
    "pt": "PT",
    "susco": "Susco",
    "pure": "Pure",
    "sinopec": "Sinopec/Susco",
}

_FUELS = {
    "gl95": "Gasoline 95",
    "gh95": "Gasohol 95",
    "gh91": "Gasohol 91",
    "e20": "Gasohol E20",
    "e85": "Gasohol E85",
    "ds": "Diesel",
    "pds": "Premium diesel",
    "dsb20": "Diesel B20",
    "dsb10": "Diesel B10",
    "gs95p": "Gasohol 95 premium",
    "gs99p": "Gasohol 99 premium",
    "gl95p": "Gasoline 95 premium",
}


def _as_price(raw: object) -> float | None:
    try:
        value = float(str(raw).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def fetch_th_eppo_oil_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    payload = json.loads(resp.text.lstrip("\ufeff"))
    if payload.get("status") != "success":
        raise ValueError(f"unexpected EPPO status: {payload.get('status')!r}")

    rows: list[dict] = []
    ts = get_scrape_ts()
    for brand_key, values in (payload.get("data") or {}).items():
        brand = _BRANDS.get(brand_key, brand_key.upper())
        obs_raw = values.get(f"oil_{brand_key}_date")
        try:
            obs_date = date.fromisoformat(str(obs_raw))
        except ValueError:
            logger.warning("[%s] bad date for %s: %r", _SOURCE_KEY, brand_key, obs_raw)
            continue
        if obs_date <= cutoff:
            continue

        effective_time = values.get(f"oil_{brand_key}_time") or ""
        for fuel_key, fuel_label in _FUELS.items():
            price = _as_price(values.get(f"oil_{brand_key}_{fuel_key}"))
            if price is None:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": "Bangkok and vicinities",
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"{fuel_label}, {brand}",
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _URL,
                "notes": f"EPPO oil retail price endpoint; effective_time={effective_time}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
