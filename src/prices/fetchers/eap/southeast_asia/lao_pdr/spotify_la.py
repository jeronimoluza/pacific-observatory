"""Spotify Premium Laos — subscription plan tariff.

Scrapes the public /la/premium/ page and emits one PriceObservation per
plan tier (Individual, Student, Duo, Family). Prices are shown in USD on
the Laos locale; the fetcher records them as USD with a note.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.spotify.com/la/premium/"
_COUNTRY = "Lao PDR"
# Spotify Laos prices are denominated in USD, not LAK.
_CURRENCY = "USD"
_SOURCE_KEY = "la_spotify"
_COICOP = "09.4.2"  # Digital streaming / online content subscriptions
_UNIT = "month"

_IDENT = ["source_key", "item_name", "price_local"]

# Plan name patterns Spotify uses in their markup
_PLAN_PATTERNS = {
    "Individual": re.compile(r"individual", re.IGNORECASE),
    "Student": re.compile(r"student", re.IGNORECASE),
    "Duo": re.compile(r"duo", re.IGNORECASE),
    "Family": re.compile(r"family|premium\s+family", re.IGNORECASE),
}

_USD_PRICE_RE = re.compile(r"US\$\s*([\d.]+)|^\$\s*([\d.]+)", re.IGNORECASE)


def _extract_price(text: str) -> float | None:
    m = _USD_PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    return float(raw)


def fetch_la_spotify(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    today = datetime.now(timezone.utc).date().isoformat()
    seen: set[str] = set()
    rows: list[dict] = []

    # Walk price-containing elements and match to plan labels
    for price_tag in soup.find_all(string=_USD_PRICE_RE):
        price = _extract_price(price_tag)
        if price is None or price <= 0:
            continue
        # Walk up to find the enclosing plan card, then look for plan name
        container = price_tag.parent
        for _ in range(6):
            if container is None:
                break
            block_text = container.get_text(separator=" ", strip=True)
            for plan_name, pattern in _PLAN_PATTERNS.items():
                if pattern.search(block_text) and plan_name not in seen:
                    seen.add(plan_name)
                    row: dict = {
                        "observation_date": today,
                        "period_kind": "effective_from",
                        "country": _COUNTRY,
                        "source_key": _SOURCE_KEY,
                        "item_name": f"Spotify Premium {plan_name}",
                        "price_local": price,
                        "currency": _CURRENCY,
                        "unit": _UNIT,
                        "coicop_code": _COICOP,
                        "source_url": _URL,
                        "notes": "USD-denominated on Spotify Laos locale; apply BOL FX for LAK",
                        "scrape_ts": get_scrape_ts(),
                        "observation_hash": None,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)
                    break
            if plan_name in seen:
                break
            container = container.parent

    return pd.DataFrame(rows) if rows else None
