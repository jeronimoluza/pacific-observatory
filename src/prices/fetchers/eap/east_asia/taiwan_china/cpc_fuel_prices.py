"""CPC Corporation Taiwan main fuel-product list prices."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = (
    "https://vipmbr.cpc.com.tw/cpcstn/listpricewebservice.asmx/"
    "getCPCMainProdListPrice_English_XML"
)
_COUNTRY = "Taiwan"
_CURRENCY = "TWD"
_SOURCE_KEY = "tw_cpc_fuel_prices"
_SOURCE_URL = "https://data.gov.tw/en/datasets/6339"
_COICOP = "07.2.2"
_IDENT = ["source_key", "observation_date", "product_id", "item_name"]


def _roc_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if len(raw) != 7 or not raw.isdigit():
        return None
    year = int(raw[:3]) + 1911
    return date(year, int(raw[3:5]), int(raw[5:7]))


def fetch_tw_cpc_fuel_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    ts = get_scrape_ts()
    rows: list[dict] = []
    for table in root.findall(".//Table"):
        product_id = table.findtext("產品編號") or ""
        name = table.findtext("產品名稱") or ""
        raw_price = table.findtext("參考牌價_金額") or ""
        unit = table.findtext("計價單位") or ""
        raw_date = table.findtext("牌價生效日期") or ""
        if "per liter" not in unit.lower():
            continue
        obs_date = _roc_date(raw_date)
        if obs_date is None or obs_date <= cutoff:
            continue
        try:
            price = float(raw_price)
        except ValueError:
            continue
        if price <= 0:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": name.strip()[:500],
            "price_local": price,
            "currency": _CURRENCY,
            "unit": unit.strip() or None,
            "source_url": _URL,
            "notes": (
                f"CPC main-product list price; product_id={product_id.strip()}; "
                f"data.gov.tw dataset={_SOURCE_URL}"
            ),
            "scrape_ts": ts,
            "product_id": product_id.strip(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("product_id")
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
