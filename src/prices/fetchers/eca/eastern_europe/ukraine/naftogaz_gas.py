"""Naftogaz (naftogaz.com) — Ukraine household natural-gas tariff.

Naftogaz is the state gas supplier; its retail-supply page states the regulated
household natural-gas price (a fixed-tariff moratorium price, e.g.
7.96 UAH/m³) in the page text. Administered price, recorded as a snapshot and
accumulated by observation_hash (a new row only when the regulated rate moves).

analytical_role: tariff · coicop_classification: source_curated
Household natural gas maps to COICOP 04.5.2 (gas).
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

_URL = "https://www.naftogaz.com/en/business/retail-supply-business-unit"
_COUNTRY = "Ukraine"
_CURRENCY = "UAH"
_SOURCE_KEY = "ua_naftogaz_gas"
_COICOP = "04.5.2"  # Gas

# "7.96 UAH per cubic meter"
_PRICE_RE = re.compile(r"(\d+[.,]\d+)\s*UAH\s*per\s*cubic", re.IGNORECASE)

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_ua_naftogaz_gas(cutoff: date) -> pd.DataFrame | None:
    resp = cffi_requests.get(_URL, timeout=30, impersonate="chrome")
    resp.raise_for_status()
    text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)

    m = _PRICE_RE.search(text)
    if not m:
        logger.warning("naftogaz_gas: household gas price not found in page text")
        return None
    price = float(m.group(1).replace(",", "."))
    if not 0.1 < price < 1000:
        logger.warning("naftogaz_gas: price %.2f out of bounds", price)
        return None

    obs_date = date.today().isoformat()
    row = {
        "observation_date": obs_date,
        "period_kind": "snapshot",
        "country": _COUNTRY,
        "source_key": _SOURCE_KEY,
        "coicop_code": _COICOP,
        "item_name": "Household natural gas",
        "price_local": price,
        "currency": _CURRENCY,
        "unit": "m3",
        "source_url": _URL,
        "notes": "Regulated household gas tariff (fixed-price moratorium)",
        "scrape_ts": get_scrape_ts(),
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return pd.DataFrame([row])
