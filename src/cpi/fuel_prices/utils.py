"""Shared utilities: hashing, HTTP session, template helpers."""

import hashlib
from datetime import date, datetime, timezone

import pandas as pd
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MONTH_MAP_EN = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def get_scrape_ts() -> str:
    """Return current UTC timestamp string — call per-fetch, not at import time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_hash(row: dict) -> str:
    """Generate a SHA-256 observation_hash from key identifying fields.

    Uses \\x00 as separator to prevent hash collisions from pipe-containing values.
    """
    key = "\x00".join(
        [
            str(row.get("country", "")),
            str(row.get("source_key", "")),
            str(row.get("observation_date", "")),
            str(row.get("fuel_product", "")),
            str(row.get("subnational_area", "")),
            str(row.get("city", "")),
            str(row.get("address", "")),
            str(row.get("price_local", "")),
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def safe_last_date(df: pd.DataFrame, source_key: str, fallback: date) -> date:
    """Return max observation_date for source_key, or fallback if absent."""
    src = df[df["source_key"] == source_key]
    if src.empty:
        return fallback
    ts = pd.to_datetime(src["observation_date"]).max()
    return fallback if pd.isna(ts) else ts.date()


def make_template(**kwargs) -> dict:
    """Build a row template dict for a new observation row.

    Only includes the 12 lean COLUMNS. Extra kwargs (e.g. fuel_family, source_name)
    are accepted for convenience and will be present in the returned dict, but
    save_fuel_csv() will drop them when writing to disk.
    """
    defaults = {
        "observation_date": None,
        "country": None,
        "subnational_area": None,
        "city": None,
        "address": None,
        "fuel_product": None,
        "price_local": None,
        "currency": None,
        "unit": "L",
        "source_key": None,
        "scrape_ts": get_scrape_ts(),
        "observation_hash": None,
    }
    defaults.update(kwargs)
    return defaults
