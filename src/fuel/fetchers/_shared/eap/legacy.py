"""Helpers shared by EAP fetchers ported from the legacy pacific-observatory pipeline.

Kept byte-compatible with ``src/cpi/fuel_prices/utils.py`` in the legacy repo so a
ported fetcher emits the same rows (and the same observation_hash) as before.
"""

from datetime import datetime, timezone

import requests

from core.hashing import observation_hash

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MONTH_MAP_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_HASH_FIELDS = [
    "country", "source_key", "observation_date", "fuel_product",
    "subnational_area", "city", "address", "price_local",
]


def get_scrape_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def make_hash(row: dict) -> str:
    return observation_hash(row, _HASH_FIELDS)


def make_template(**kwargs) -> dict:
    defaults = {
        "observation_date": None, "country": None, "subnational_area": None,
        "city": None, "address": None, "fuel_product": None, "price_local": None,
        "currency": None, "unit": "L", "source_key": None,
        "scrape_ts": get_scrape_ts(), "observation_hash": None,
    }
    defaults.update(kwargs)
    return defaults
