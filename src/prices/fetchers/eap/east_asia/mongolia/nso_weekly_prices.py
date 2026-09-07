"""Mongolia NSO weekly prices of main products and gasoline.

The National Statistics Office PxWeb table DT_NSO_0600_001V4 publishes weekly
Ulaanbaatar prices for staple foods and fuel products. The endpoint is open
JSON over HTTPS, but the server certificate chain is incomplete from this
environment, so requests intentionally disable verification for this host only.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import urllib3

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = (
    "https://data.1212.mn/api/v1/en/NSO/Economy,%20environment/"
    "Consumer%20Price%20Index/DT_NSO_0600_001V4.px"
)
_SOURCE_URL = (
    "https://data.1212.mn/pxweb/en/NSO/"
    "NSO__Economy%2C%20environment__Consumer%20Price%20Index/"
    "DT_NSO_0600_001V4.px/"
)
_COUNTRY = "Mongolia"
_SUBNATIONAL_AREA = "Ulaanbaatar city"
_CURRENCY = "MNT"
_SOURCE_KEY = "mn_nso_weekly_prices"
_UNIT = "togrogs"
_IDENT = ["source_key", "observation_date", "item_name"]


def _clean_label(value: str) -> str:
    return " ".join(str(value).split())


def _parse_date(label: str) -> date | None:
    try:
        return pd.to_datetime(str(label).replace(".", "-")).date()
    except (TypeError, ValueError):
        return None


def _metadata(session) -> dict:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = session.get(_API_URL, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.json()


def _post(session, product_values: list[str], time_values: list[str]) -> dict:
    query = {
        "query": [
            {
                "code": "Бүтээгдэхүүн",
                "selection": {"filter": "item", "values": product_values},
            },
            {
                "code": "Хугацаа",
                "selection": {"filter": "item", "values": time_values},
            },
        ],
        "response": {"format": "JSON-stat2"},
    }
    resp = session.post(_API_URL, json=query, timeout=60, verify=False)
    resp.raise_for_status()
    return resp.json()


def fetch_mn_nso_weekly_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    meta = _metadata(session)
    variables = {v["code"]: v for v in meta.get("variables", [])}
    products = variables.get("Бүтээгдэхүүн") or {}
    times = variables.get("Хугацаа") or {}

    product_values = [
        str(v) for v in products.get("values", []) if str(v).strip() != ""
    ]
    product_labels = {
        str(v): _clean_label(label)
        for v, label in zip(products.get("values", []), products.get("valueTexts", []))
    }

    selected_time_values: list[str] = []
    time_labels: dict[str, str] = {}
    for value, label in zip(times.get("values", []), times.get("valueTexts", [])):
        obs_date = _parse_date(label)
        if obs_date is None or obs_date <= cutoff:
            continue
        key = str(value)
        selected_time_values.append(key)
        time_labels[key] = obs_date.isoformat()

    if not product_values or not selected_time_values:
        logger.info("[%s] no new product/time cells after cutoff %s", _SOURCE_KEY, cutoff)
        return None

    payload = _post(session, product_values, selected_time_values)
    values = payload.get("value") or []
    size = payload.get("size") or [len(product_values), len(selected_time_values)]
    if len(size) != 2:
        logger.warning("[%s] unexpected JSON-stat size: %s", _SOURCE_KEY, size)
        return None

    product_count, time_count = int(size[0]), int(size[1])
    ts = get_scrape_ts()
    rows: list[dict] = []
    for product_idx in range(product_count):
        product_code = product_values[product_idx]
        item_name = product_labels.get(product_code)
        if not item_name:
            continue
        for time_idx in range(time_count):
            value_idx = product_idx * time_count + time_idx
            if value_idx >= len(values):
                continue
            raw_price = values[value_idx]
            if raw_price is None:
                continue
            try:
                price = float(raw_price)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            obs_date = time_labels.get(selected_time_values[time_idx])
            if not obs_date:
                continue
            row = {
                "observation_date": obs_date,
                "period_kind": "weekly",
                "country": _COUNTRY,
                "subnational_area": _SUBNATIONAL_AREA,
                "source_key": _SOURCE_KEY,
                "coicop_code": None,
                "item_name": item_name,
                "price_local": price,
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _SOURCE_URL,
                "notes": "NSO weekly Ulaanbaatar main products and gasoline table",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info("[%s] parsed %d rows after cutoff %s", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
