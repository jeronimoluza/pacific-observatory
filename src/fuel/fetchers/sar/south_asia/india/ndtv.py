"""NDTV India fuel price tables (live + Wayback) — petrol and diesel.

NDTV publishes a single page per fuel type with one row per city/district.
We restrict to a small set of major cities so the build dataset stays focused
and historical comparisons are tractable.
"""

import logging
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session
from fuel.fetchers._shared.sar.wayback import iterate_snapshots

logger = logging.getLogger(__name__)

_PETROL_URL = "https://www.ndtv.com/fuel-prices/petrol-price-in-india"
_DIESEL_URL = "https://www.ndtv.com/fuel-prices/diesel-price-in-india"

_COUNTRY = "India"
_CURRENCY = "INR"

# Browser-like Accept headers — NDTV returns 403 to plain UA-only requests.
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# Major Indian metros — keeps the time series small and comparable.
# Map raw NDTV row label → canonical city name. NDTV uses "Greater Mumbai" /
# "Mumbai City" (identical prices) for Mumbai; we keep "Greater Mumbai" only
# so the series isn't duplicated.
_CITY_MAP = {
    "Ahmedabad": "Ahmedabad",
    "Bangalore": "Bangalore",
    "Chennai": "Chennai",
    "Greater Mumbai": "Mumbai",
    "Hyderabad": "Hyderabad",
    "Kolkata": "Kolkata",
    "Lucknow": "Lucknow",
    "New Delhi": "New Delhi",
    "Pune": "Pune",
}


def _parse_table(html: str, label: str) -> list[tuple[str, float]]:
    """Return [(canonical_city, price), …] for cities in `_CITY_MAP`."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []

    pairs: list[tuple[str, float]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        raw_city = cells[0].get_text(" ", strip=True)
        canonical = _CITY_MAP.get(raw_city)
        if canonical is None:
            continue
        price_text = cells[1].get_text(" ", strip=True).replace(",", "")
        # Format: "108.83 ₹/L"
        token = price_text.split()[0] if price_text else ""
        try:
            price = float(token)
        except ValueError:
            logger.debug(
                "[ndtv_%s] unparseable price for %s: %s", label, canonical, price_text
            )
            continue
        if price <= 0:
            continue
        pairs.append((canonical, price))
    return pairs


def _row(
    observation_date: date, label: str, source_key: str, city: str, price: float
) -> dict:
    return {
        "observation_date": observation_date.strftime("%Y-%m-%d"),
        "country": _COUNTRY,
        "fuel_product": label,
        "price_local": price,
        "currency": _CURRENCY,
        "source_key": source_key,
        "unit": "L",
        "city": city,
    }


def _fetch_live(url: str, label: str, source_key: str) -> list[dict]:
    session = make_session(**_HEADERS)
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:
        # Akamai bot-blocks plain HTTP clients; Wayback handles backfill, so non-fatal.
        logger.warning(
            "[ndtv_%s] live fetch unavailable (%s) — using Wayback only", label, exc
        )
        return []
    today = datetime.now(timezone.utc).date()
    return [
        _row(today, label, source_key, city, price)
        for city, price in _parse_table(resp.text, label)
    ]


def _fetch(url: str, label: str, source_key: str, cutoff: date) -> pd.DataFrame | None:
    seen: set[tuple[str, str]] = set()
    all_rows: list[dict] = []

    for snap_date, html in iterate_snapshots(url, cutoff, collapse_digits=8):
        if snap_date <= cutoff:
            continue
        for city, price in _parse_table(html, label):
            row = _row(snap_date, label, source_key, city, price)
            key = (row["observation_date"], row["city"])
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)

    for row in _fetch_live(url, label, source_key):
        key = (row["observation_date"], row["city"])
        if key in seen:
            continue
        seen.add(key)
        all_rows.append(row)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)


def fetch_in_ndtv_petrol(cutoff: date) -> pd.DataFrame | None:
    """Fetch India petrol prices from NDTV (Wayback backfill + live current)."""
    return _fetch(_PETROL_URL, "Petrol", "ndtv_in_petrol", cutoff)


def fetch_in_ndtv_diesel(cutoff: date) -> pd.DataFrame | None:
    """Fetch India diesel prices from NDTV (Wayback backfill + live current)."""
    return _fetch(_DIESEL_URL, "Diesel", "ndtv_in_diesel", cutoff)
