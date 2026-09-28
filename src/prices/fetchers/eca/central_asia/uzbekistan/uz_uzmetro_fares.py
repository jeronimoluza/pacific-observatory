"""Tashkent Metro (uzmetro.uz) — integrated metro/bus transport card issuance
prices and per-ride fares. Static server-rendered page, values embedded in an
inline i18n JSON blob (no separate API).
"""

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://uzmetro.uz/"
_COUNTRY = "Uzbekistan"
_CURRENCY = "UZS"
_SOURCE_KEY = "uz_uzmetro_fares"
_COICOP = "07.3.2"  # Passenger transport by road — combined metro+bus urban fare product

_IDENT = ["source_key", "observation_date", "item_name"]

# Card issuance types: (card key, unit)
_CARD_KEYS = [1, 2, 3, 4]

# Per-ride fare labels, keyed off the exact i18n keys observed live 2026-09-28.
# Each entry: (label key with the amount, human-readable item name).
_FARE_KEYS = [
    ("tolov10", "Yo'l haqi — kontaktsiz to'lov (metro/avtobus)"),
    ("tolov17", "Yo'l haqi — QR-bilet (naqd)"),
    ("tolov36", "Yo'l haqi — ATTO karta"),
]


def _num(text: str) -> float | None:
    m = re.search(r"[\d][\d.,]*", text)
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", ""))


def fetch_uz_uzmetro_fares(cutoff: date) -> pd.DataFrame | None:
    today = datetime.now(timezone.utc).date()
    if today <= cutoff:
        return None

    session = get_session()
    resp = session.get(_PAGE_URL, timeout=30)
    resp.raise_for_status()
    t = resp.text

    rows = []

    for i in _CARD_KEYS:
        name_m = re.search(r'\\"card%d_name\\":\\"([^\\"]+)\\"' % i, t)
        price_m = re.search(r'\\"card%d_price\\":\\"([^\\"]+)\\"' % i, t)
        if not name_m or not price_m:
            continue
        price = _num(price_m.group(1))
        if price is None:
            continue
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": f"Transport karta — {name_m.group(1)}",
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "each",
            "coicop_code": _COICOP,
            "source_url": _PAGE_URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    for key, item_name in _FARE_KEYS:
        m = re.search(r'\\"%s\\":\\"([^\\"]*)\\"' % key, t)
        if not m:
            logger.warning("uzmetro.uz fare key %r not found on page — dropping", key)
            continue
        price = _num(m.group(1))
        if price is None:
            continue
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "ride",
            "coicop_code": _COICOP,
            "source_url": _PAGE_URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
