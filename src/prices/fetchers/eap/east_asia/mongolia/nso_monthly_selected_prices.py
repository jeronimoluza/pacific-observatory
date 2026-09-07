"""Mongolia NSO monthly selected prices of goods and services.

The National Statistics Office PxWeb table DT_NSO_0600_019V1 publishes monthly
prices for selected goods and services across Ulaanbaatar and aimags. The open
API returns JSON-stat2; as with the weekly NSO table, the server certificate
chain is incomplete from this environment, so requests disable verification for
data.1212.mn only.
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
    "Consumer%20Price%20Index/DT_NSO_0600_019V1.px"
)
_SOURCE_URL = (
    "https://data.1212.mn/pxweb/en/NSO/"
    "NSO__Economy%2C%20environment__Consumer%20Price%20Index/"
    "DT_NSO_0600_019V1.px/"
)
_COUNTRY = "Mongolia"
_CURRENCY = "MNT"
_SOURCE_KEY = "mn_nso_monthly_selected_prices"
_UNIT = "togrogs"
_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]


def _clean_label(value: str) -> str:
    return " ".join(str(value).split())


def _parse_month(label: str) -> date | None:
    try:
        ts = pd.to_datetime(f"{label}-01")
    except (TypeError, ValueError):
        return None
    return ts.date()


def _metadata(session) -> dict:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = session.get(_API_URL, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.json()


def _post(
    session,
    region_values: list[str],
    item_values: list[str],
    month_values: list[str],
) -> dict:
    query = {
        "query": [
            {
                "code": "Бүс",
                "selection": {"filter": "item", "values": region_values},
            },
            {
                "code": "Бараа, үйлчилгээ",
                "selection": {"filter": "item", "values": item_values},
            },
            {
                "code": "Сар",
                "selection": {"filter": "item", "values": month_values},
            },
        ],
        "response": {"format": "JSON-stat2"},
    }
    resp = session.post(_API_URL, json=query, timeout=90, verify=False)
    resp.raise_for_status()
    return resp.json()


def _dimension(meta: dict, code: str) -> dict:
    for variable in meta.get("variables", []):
        if variable.get("code") == code:
            return variable
    raise KeyError(f"NSO PxWeb dimension not found: {code}")


def fetch_mn_nso_monthly_selected_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    meta = _metadata(session)

    regions = _dimension(meta, "Бүс")
    items = _dimension(meta, "Бараа, үйлчилгээ")
    months = _dimension(meta, "Сар")

    region_values = [str(v) for v in regions.get("values", []) if str(v).strip()]
    region_labels = {
        str(v): _clean_label(label)
        for v, label in zip(regions.get("values", []), regions.get("valueTexts", []))
    }
    item_values = [str(v) for v in items.get("values", []) if str(v).strip()]
    item_labels = {
        str(v): _clean_label(label)
        for v, label in zip(items.get("values", []), items.get("valueTexts", []))
    }

    selected_month_values: list[str] = []
    month_labels: dict[str, str] = {}
    for value, label in zip(months.get("values", []), months.get("valueTexts", [])):
        obs_date = _parse_month(str(label))
        if obs_date is None or obs_date <= cutoff:
            continue
        key = str(value)
        selected_month_values.append(key)
        month_labels[key] = obs_date.isoformat()

    if not region_values or not item_values or not selected_month_values:
        logger.info("[%s] no new cells after cutoff %s", _SOURCE_KEY, cutoff)
        return None

    payload = _post(session, region_values, item_values, selected_month_values)
    values = payload.get("value") or []
    size = payload.get("size") or [
        len(region_values),
        len(item_values),
        len(selected_month_values),
    ]
    if len(size) != 3:
        logger.warning("[%s] unexpected JSON-stat size: %s", _SOURCE_KEY, size)
        return None

    region_count, item_count, month_count = (int(size[0]), int(size[1]), int(size[2]))
    ts = get_scrape_ts()
    rows: list[dict] = []
    for region_idx in range(region_count):
        region_code = region_values[region_idx]
        subnational_area = region_labels.get(region_code)
        if not subnational_area:
            continue
        for item_idx in range(item_count):
            item_code = item_values[item_idx]
            item_name = item_labels.get(item_code)
            if not item_name:
                continue
            for month_idx in range(month_count):
                value_idx = (
                    region_idx * item_count * month_count
                    + item_idx * month_count
                    + month_idx
                )
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
                obs_date = month_labels.get(selected_month_values[month_idx])
                if not obs_date:
                    continue
                row = {
                    "observation_date": obs_date,
                    "period_kind": "monthly",
                    "country": _COUNTRY,
                    "subnational_area": subnational_area,
                    "source_key": _SOURCE_KEY,
                    "coicop_code": None,
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": _UNIT,
                    "source_url": _SOURCE_URL,
                    "notes": "NSO selected goods and services monthly price table",
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

    logger.info("[%s] parsed %d rows after cutoff %s", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
