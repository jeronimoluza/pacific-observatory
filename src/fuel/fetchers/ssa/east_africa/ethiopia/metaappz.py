"""MetaAppz Ethiopia monthly retail fuel prices for Addis Ababa.

The aggregator at ``https://www.metaappz.com/Tools/Ethiopia_Fuel_Price``
publishes a static HTML table (``id="fuelPriceTable"``) of monthly Petrol
and Diesel retail prices in ETB per liter for Addis Ababa. The fetcher
parses that table directly — no PDFs, no OCR.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://www.metaappz.com/Tools/Ethiopia_Fuel_Price"
_COUNTRY = "Ethiopia"
_CURRENCY = "ETB"
_SOURCE_KEY = "metaappz_et_monthly"

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_DATE_RE = re.compile(r"^([A-Za-z]{3,})\s+(\d{4})$")


def _parse_month(text: str) -> date | None:
    match = _DATE_RE.match(text.strip())
    if not match:
        return None
    month = _MONTHS.get(match.group(1)[:3].lower())
    if not month:
        return None
    try:
        return date(int(match.group(2)), month, 1)
    except ValueError:
        return None


def _parse_price(text: str) -> float | None:
    cleaned = text.replace(",", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if 1 <= value <= 1000 else None


def fetch_metaappz_et(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    try:
        resp = session.get(_URL, timeout=45)
    except Exception:
        logger.exception("[metaappz_et] HTML request failed: %s", _URL)
        return None
    if resp.status_code != 200:
        logger.warning("[metaappz_et] HTTP %s for %s", resp.status_code, _URL)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="fuelPriceTable") or soup.find("table")
    if table is None:
        logger.warning("[metaappz_et] no price table found at %s", _URL)
        return None

    rows: list[dict] = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        obs_date = _parse_month(cells[0].get_text(strip=True))
        petrol = _parse_price(cells[1].get_text(strip=True))
        diesel = _parse_price(cells[2].get_text(strip=True))
        if obs_date is None or obs_date <= cutoff:
            continue
        for product, price in (("Petrol", petrol), ("Diesel", diesel)):
            if price is None:
                continue
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                }
            )

    if not rows:
        logger.info("[metaappz_et] no rows after cutoff %s", cutoff)
        return None
    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )


__all__ = ["fetch_metaappz_et"]
