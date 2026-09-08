"""PTT Oil and Retail Business (PTTOR, Thailand) — national retail fuel prices.

PTTOR runs the "PTT Station" forecourt network. Its public oil-price page
(https://www.pttor.com/news/oil-price) embeds a `latestFallbackPrices`
JavaScript object directly in the page HTML — a client-side fallback shown
while the page's live AJAX widget (a separate WordPress admin-ajax action,
`fetch_regional_oil_prices`, which needs province/district/month/year
parameters for the *regional* history table) loads. This fetcher reads the
simpler embedded fallback blob rather than reverse-engineering the regional
AJAX call, since it already carries current national retail prices with a
per-item date:

    var latestFallbackPrices = {"<Thai fuel name>": {"price": 34.57,
        "priceDate": "2026-09-02T05:00", "priceTimestamp": ...}, ...};

Confirmed live 2026-09-06 with plain `requests` (no TLS impersonation
needed). All 9 items returned (ดีเซล B20/ดีเซล, เบนซินแก๊สโซฮอล์ E20/91/95,
เบนซิน, Super Power GSH95/Diesel/X99) are vehicle motor fuels — narrow,
single-COICOP (07.2.2) source_curated fetcher.

Distinct from bangchak_fuel.py (Bangchak Corporation) — two independent
national fuel retailers with independently published retail prices, not the
same source under two names.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.pttor.com/news/oil-price"
_COUNTRY = "Thailand"
_CURRENCY = "THB"
_SOURCE_KEY = "th_pttor_fuel"
_UNIT = "L"
_IDENT = ["source_key", "observation_date", "item_name"]

# COICOP 07.2.2 leaves: .1 Diesel, .2 Petrol (gasohol = petrol/ethanol blend).
# "Super Power Diesel" and "Super Power X99" are both PTT premium diesel
# grades; "Super Power GSH95" is a premium gasohol-95 (petrol) grade.
_COICOP_MAP = {
    "ดีเซล B20": "07.2.2.1",  # Diesel B20
    "ดีเซล": "07.2.2.1",  # Diesel
    "เบนซินแก๊สโซฮอล์ E20": "07.2.2.2",  # Gasohol E20
    "เบนซินแก๊สโซฮอล์ 91": "07.2.2.2",  # Gasohol 91
    "เบนซินแก๊สโซฮอล์ 95": "07.2.2.2",  # Gasohol 95
    "เบนซิน": "07.2.2.2",  # plain petrol
    "Super Power GSH95": "07.2.2.2",
    "Super Power Diesel": "07.2.2.1",
    "Super Power X99": "07.2.2.1",
}

_BLOB_RE = re.compile(r"var\s+latestFallbackPrices\s*=\s*(\{.*?\});", re.S)


def fetch_th_pttor_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_PAGE_URL, timeout=30)
    resp.raise_for_status()

    m = _BLOB_RE.search(resp.text)
    if not m:
        logger.warning("pttor oil-price page: latestFallbackPrices blob not found")
        return None

    try:
        blob = json.loads(m.group(1))
    except json.JSONDecodeError:
        logger.warning("pttor oil-price page: could not parse latestFallbackPrices JSON")
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    for name, entry in blob.items():
        price = entry.get("price")
        raw_date = entry.get("priceDate")
        if price is None or not raw_date:
            continue
        coicop = _COICOP_MAP.get(name)
        if not coicop:
            logger.warning("No COICOP mapping for pttor item %r — dropping row", name)
            continue
        try:
            obs_date = datetime.fromisoformat(raw_date).date()
        except ValueError:
            continue
        if obs_date <= cutoff:
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
            "source_url": _PAGE_URL,
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("No fuel rows extracted from pttor.com latestFallbackPrices")
        return None
    return pd.DataFrame(rows)
