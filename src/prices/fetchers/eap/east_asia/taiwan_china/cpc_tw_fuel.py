"""Taiwan — CPC Corporation (state oil company) retail fuel list prices.

CPC (Taiwan) Corporation, the state-owned petroleum company, publishes its
current retail/list prices for gasoline and diesel through a genuine open
REST API (no API key, no auth) registered on Taiwan's national open-data
portal (data.gov.tw dataset 6339, "中油主產品牌價"):

  https://vipmbr.cpc.com.tw/openData/MainProdListPrice_English

Verified live 2026-09-06: returns a JSON array of ~7-13 records (retail
gasoline/diesel grades + marine fuel + fuel-oil grades), each carrying a
"list price effective date" (`牌價生效日期`) in ROC (Republic of China)
calendar YYYMMDD format (e.g. "1150907" = ROC year 115 = 2026, month 09, day
07). CPC updates this weekly under Taiwan's floating fuel-price mechanism.

This fetcher keeps only the four retail-pump gasoline/diesel grades that
consumers actually buy at CPC's self-service stations (`銷售對象` ==
"Own Used" / 一般自用客戶, package == "Bulk"/散裝) — i.e. the four grades in
the site's own "今日汽柴油零售價格" (today's retail gasoline/diesel price)
widget. Marine fuel, fuel oil, and contract/fleet-card prices are excluded:
they are wholesale/industrial, not the retail-pump price a consumer basket
should carry.

Single COICOP class (vehicle fuel) -> COICOP 07.2.2, narrow source,
short-circuits the classifier. No historical endpoint was found on this API
(swagger only exposes LPG history, not gasoline/diesel history) — this
fetcher snapshots the current list price each run; `fallback_date` is set
recent since only the live snapshot is available on first run.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Taiwan, China"
_CURRENCY = "TWD"
_SOURCE_KEY = "cpc_tw_fuel"
_SOURCE_URL = "https://www.cpc.com.tw/cp.aspx?n=38"
_API_URL = "https://vipmbr.cpc.com.tw/openData/MainProdListPrice_English"
_IDENT = ["source_key", "observation_date", "item_name"]

# Retail-pump grades to keep (product name -> (unit, COICOP leaf)).
# Everything else in the payload (marine fuel, fuel oil, fleet-card
# contract prices) is dropped. Leaves: 07.2.2.1 Diesel, 07.2.2.2 Petrol.
_RETAIL_GRADES = {
    "98 Unleaded Gasoline": ("L", "07.2.2.2"),
    "95 Unleaded Gasoline": ("L", "07.2.2.2"),
    "92 Unleaded Gasoline": ("L", "07.2.2.2"),
    "95E3 Gasohol": ("L", "07.2.2.2"),
    "Premium Diesel": ("L", "07.2.2.1"),
}


def _parse_roc_date(raw: str) -> date | None:
    """'1150907' (ROC YYYMMDD) -> date(2026, 9, 7)."""
    m = re.fullmatch(r"(\d{2,3})(\d{2})(\d{2})", raw.strip())
    if not m:
        return None
    roc_year, month, day = m.groups()
    try:
        return date(int(roc_year) + 1911, int(month), int(day))
    except ValueError:
        return None


def fetch_cpc_tw_fuel(cutoff: date) -> pd.DataFrame | None:
    resp = curl_requests.get(_API_URL, impersonate="chrome124", timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list) or not payload:
        logger.warning("[%s] unexpected payload shape: %r", _SOURCE_KEY, payload)
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []

    for rec in payload:
        name = rec.get("產品名稱")
        if name not in _RETAIL_GRADES:
            continue
        if rec.get("銷售對象") != "Own Used":
            continue
        obs_date = _parse_roc_date(str(rec.get("牌價生效日期", "")))
        if obs_date is None or obs_date <= cutoff:
            continue
        raw_price = rec.get("參考牌價_金額")
        if raw_price in (None, ""):
            continue
        unit, coicop_code = _RETAIL_GRADES[name]
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop_code,
            "item_name": f"{name}, pump price",
            "price_local": float(raw_price),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _SOURCE_URL,
            "notes": (
                "CPC Corporation Taiwan (state oil company) self-service "
                "station retail list price, via CPC's open-data REST API "
                "(data.gov.tw dataset 6339); tax-inclusive."
            ),
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.info(
            "[%s] all observation dates <= cutoff %s -- nothing new",
            _SOURCE_KEY,
            cutoff,
        )
        return None

    return pd.DataFrame(rows)
