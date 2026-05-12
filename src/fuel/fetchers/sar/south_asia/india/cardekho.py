"""CarDekho India retail fuel prices (live + Wayback) — Petrol, Diesel, CNG.

CarDekho's `/fuel-price` page renders three sections (Petrol, Diesel, CNG)
keyed by `data-track-section` and tabled as `City | ₹price`. We pull all
three from the same HTML, so every snapshot/live hit yields three series.

CarDekho serves directly from origin (no Akamai/Cloudflare gate), so the
live path is a normal browser-like GET. Wayback CDX has continuous coverage
from 2024-01 onward — useful as a fill-in for sources blocked at the edge
(e.g. NDTV, which 403s past 2024-10).
"""

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session
from fuel.fetchers._shared.sar.wayback import iterate_snapshots

logger = logging.getLogger(__name__)

_URL = "https://www.cardekho.com/fuel-price"
_COUNTRY = "India"
_CURRENCY = "INR"

# fuel label (matches data-track-section attribute) → (source_key, unit)
_FUEL_META = {
    "Petrol": ("cardekho_in_petrol", "L"),
    "Diesel": ("cardekho_in_diesel", "L"),
    "CNG": ("cardekho_in_cng", "kg"),
}


def _parse_section(html: str, fuel: str) -> list[tuple[str, float]]:
    """Return [(city, price), …] from the named section's city table."""
    soup = BeautifulSoup(html, "lxml")
    section = soup.find("div", attrs={"data-track-section": fuel})
    if section is None:
        return []
    table = section.find("table")
    if table is None:
        return []

    pairs: list[tuple[str, float]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        city = cells[0].get_text(" ", strip=True)
        price_text = cells[1].get_text(" ", strip=True).replace(",", "")
        m = re.search(r"(\d+(?:\.\d+)?)", price_text)
        if not m or not city or city.lower() == "city":
            continue
        try:
            price = float(m.group(1))
        except ValueError:
            continue
        if price <= 0:
            continue
        pairs.append((city, price))
    return pairs


def _row(observation_date: date, fuel: str, city: str, price: float) -> dict:
    source_key, unit = _FUEL_META[fuel]
    return {
        "observation_date": observation_date.strftime("%Y-%m-%d"),
        "country": _COUNTRY,
        "fuel_product": fuel,
        "price_local": price,
        "currency": _CURRENCY,
        "source_key": source_key,
        "unit": unit,
        "city": city,
    }


def _fetch_live(fuel: str) -> list[dict]:
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[cardekho_%s] live fetch failed", fuel.lower())
        return []
    today = datetime.now(timezone.utc).date()
    return [
        _row(today, fuel, city, price)
        for city, price in _parse_section(resp.text, fuel)
    ]


def _fetch(fuel: str, cutoff: date) -> pd.DataFrame | None:
    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []

    for snap_date, html in iterate_snapshots(_URL, cutoff, collapse_digits=8):
        if snap_date <= cutoff:
            continue
        for city, price in _parse_section(html, fuel):
            row = _row(snap_date, fuel, city, price)
            key = (row["observation_date"], row["city"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    for row in _fetch_live(fuel):
        key = (row["observation_date"], row["city"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)


def fetch_in_cardekho_petrol(cutoff: date) -> pd.DataFrame | None:
    """Fetch India petrol city prices from CarDekho (Wayback backfill + live)."""
    return _fetch("Petrol", cutoff)


def fetch_in_cardekho_diesel(cutoff: date) -> pd.DataFrame | None:
    """Fetch India diesel city prices from CarDekho (Wayback backfill + live)."""
    return _fetch("Diesel", cutoff)


def fetch_in_cardekho_cng(cutoff: date) -> pd.DataFrame | None:
    """Fetch India CNG city prices from CarDekho (Wayback backfill + live)."""
    return _fetch("CNG", cutoff)
