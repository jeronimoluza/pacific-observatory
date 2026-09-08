"""Bangchak Corporation (Thailand) — national retail fuel prices.

Bangchak (one of Thailand's largest fuel retailers, ~2,000 forecourts) exposes
an unauthenticated JSON API behind its public oil-price widget:

    GET https://www.bangchak.co.th/api/oilprice

Confirmed live 2026-09-06 with plain `requests` (no TLS impersonation
needed — the site's Radware WAF challenges the HTML front end but not this
API path). Returns `data.items[]`, each carrying `OilNameEng`, `PriceToday`
(THB/L, effective today), `PriceYesterday`, `PriceTomorrow`. There is no
per-row date field — `PriceToday` is a same-day snapshot, so this fetcher
stamps `observation_date` with the fetch date and `period_kind: snapshot`.

All 8 products returned (2026-09-06: DIESEL B20, Hi Diesel S, Hi Premium
Diesel Plus, Hi Premium 98 Plus, Gasohol E85/E20/91/95 S EVO) are vehicle
motor fuels — no kerosene/LPG in the payload — so this is a narrow,
single-COICOP (07.2.2) source_curated fetcher.

pttor.com (PTT Oil and Retail Business) is a separate, distinct national
fuel retailer with its own independent price feed — see
`src/prices/fetchers/eap/southeast_asia/thailand/pttor_fuel.py`. The two are
not duplicates.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = "https://www.bangchak.co.th/api/oilprice"
_SOURCE_URL = "https://www.bangchak.co.th/en/oilprice"
_COUNTRY = "Thailand"
_CURRENCY = "THB"
_SOURCE_KEY = "th_bangchak_fuel"
_UNIT = "L"
_IDENT = ["source_key", "observation_date", "item_name"]

# COICOP 07.2.2 leaves: .1 Diesel, .2 Petrol (gasohol = petrol/ethanol blend).
_COICOP_MAP = {
    "DIESEL B20": "07.2.2.1",
    "Hi Diesel S": "07.2.2.1",
    "Hi Premium Diesel Plus": "07.2.2.1",
    "Hi Premium 98 Plus": "07.2.2.2",
    "Gasohol E85 S EVO": "07.2.2.2",
    "Gasohol E20 S EVO": "07.2.2.2",
    "Gasohol 91 S EVO": "07.2.2.2",
    "Gasohol 95 S EVO": "07.2.2.2",
}


def fetch_th_bangchak_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    # Counter-intuitive but measured: Radware's bot-challenge on this host
    # fires on ANY declared User-Agent (browser-style or the shared
    # "pacific-observatory/prices" default) and passes only the bare
    # library default ("python-requests/x.y"). Drop the override.
    session.headers.pop("User-Agent", None)
    resp = session.get(_API_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("code") != 200:
        logger.warning("Bangchak oilprice API reported non-200 code: %s", payload)
        return None

    items = (payload.get("data") or {}).get("items") or []
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    for it in items:
        name = it.get("OilNameEng")
        price = it.get("PriceToday")
        if not name or price is None:
            continue
        coicop = _COICOP_MAP.get(name)
        if not coicop:
            logger.warning("No COICOP mapping for Bangchak item %r — dropping row", name)
            continue
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": _UNIT,
            "coicop_code": coicop,
            "source_url": _SOURCE_URL,
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("No fuel rows extracted from Bangchak oilprice API")
        return None
    return pd.DataFrame(rows)
