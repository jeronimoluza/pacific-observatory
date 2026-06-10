"""Kyivvodokanal (vodokanal.kiev.ua) — Kyiv household water & sewerage tariff.

The Kyiv water utility publishes the regulated household tariffs for centralised
water supply (водопостачання) and wastewater drainage (водовідведення) in the
page text, e.g. 47.19 UAH/m³ each. Administered prices, recorded as snapshots
and accumulated by observation_hash.

analytical_role: tariff · coicop_classification: source_curated
Water supply -> COICOP 04.4.1; sewerage collection -> COICOP 04.4.2.

The site serves an invalid TLS chain to non-UA resolvers, so we fetch via
curl_cffi with verify disabled.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.vodokanal.kiev.ua/tarifi"
_COUNTRY = "Ukraine"
_CURRENCY = "UAH"
_SOURCE_KEY = "ua_vodokanal_water"

# Each service: "...водопостачання – 47,19 грн" / "...водовідведення – 47,19 грн"
_SERVICES = [
    ("водопостачанн", "Household water supply", "04.4.1"),
    ("водовідведенн", "Household wastewater (sewerage)", "04.4.2"),
]
_VAL_RE = r"[^\d]{0,15}(\d+[.,]\d+)\s*грн"

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_ua_vodokanal_water(cutoff: date) -> pd.DataFrame | None:
    resp = cffi_requests.get(_URL, timeout=30, impersonate="chrome", verify=False)
    resp.raise_for_status()
    text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)

    obs_date = date.today().isoformat()
    rows: list[dict] = []
    for stem, item_name, coicop in _SERVICES:
        m = re.search(stem + _VAL_RE, text)
        if not m:
            logger.warning("vodokanal_water: %s tariff not found", item_name)
            continue
        price = float(m.group(1).replace(",", "."))
        if not 0.1 < price < 1000:
            logger.warning("vodokanal_water: %s price %.2f out of bounds", item_name, price)
            continue
        row = {
            "observation_date": obs_date,
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "m3",
            "source_url": _URL,
            "notes": "Regulated Kyiv household tariff",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
