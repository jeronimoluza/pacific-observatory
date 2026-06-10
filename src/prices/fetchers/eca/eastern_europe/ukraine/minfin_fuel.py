"""Minfin (index.minfin.com.ua) Ukraine retail fuel prices.

National daily average pump prices, scraped from the per-fuel-type history
tables (``/ua/markets/fuel/<slug>/``). Each page carries a rolling ~2-month
daily series in a ``table.zebra``; running daily accumulates the full history
into the output CSV (idempotent via observation_hash).

analytical_role: aggregate_proxy · coicop_classification: source_curated
All fuels map to COICOP 07.2.2 (fuels and lubricants for personal transport).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://index.minfin.com.ua/ua/markets/fuel/{slug}/"
_COUNTRY = "Ukraine"
_CURRENCY = "UAH"
_SOURCE_KEY = "ua_minfin_fuel"
_COICOP = "07.2.2"  # Fuels and lubricants for personal transport equipment

# Per-fuel-type page slug -> stable English item_name.
_FUELS = {
    "a96": "Petrol A-95 Premium",
    "a95": "Petrol A-95",
    "a92": "Petrol A-92",
    "dt": "Diesel",
    "lpg": "Autogas (LPG)",
}

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")

_IDENT = ["source_key", "observation_date", "item_name"]


def _parse_price(text: str) -> float:
    """'73,11' / '1\xa0073,11' -> float."""
    cleaned = text.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    return float(cleaned)


def _fetch_one(session, slug: str, item_name: str, cutoff: date) -> list[dict]:
    url = _BASE.format(slug=slug)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # The daily history series is the zebra-striped table; the small summary
    # table at the top of the section uses class 'line' and is skipped.
    table = soup.find("table", class_="zebra")
    if table is None:
        logger.warning("Minfin fuel: no history table for slug %r", slug)
        return []

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue  # header row
        m = _DATE_RE.search(tds[0].get_text(" ", strip=True))
        if not m:
            continue
        d, mo, y = m.groups()
        obs_date = f"{y}-{mo}-{d}"
        if date.fromisoformat(obs_date) <= cutoff:
            continue
        big = tds[1].find("big")
        if big is None:
            continue
        try:
            price = _parse_price(big.get_text())
        except ValueError:
            logger.warning("Minfin fuel: unparseable price %r (%s %s)", big.get_text(), slug, obs_date)
            continue
        if not 1.0 < price < 1000.0:  # UAH/L sanity bounds
            logger.warning("Minfin fuel: price %.2f out of bounds (%s %s)", price, slug, obs_date)
            continue
        row = {
            "observation_date": obs_date,
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "L",
            "source_url": url,
            "notes": None,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_ua_minfin_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    rows: list[dict] = []
    for slug, item_name in _FUELS.items():
        try:
            rows.extend(_fetch_one(session, slug, item_name, cutoff))
        except Exception:  # noqa: BLE001 — one bad fuel page shouldn't kill the run
            logger.exception("Minfin fuel: failed to fetch slug %r", slug)
    return pd.DataFrame(rows) if rows else None
