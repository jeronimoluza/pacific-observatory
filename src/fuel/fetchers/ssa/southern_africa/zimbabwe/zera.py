"""Zimbabwe ZERA — Current Energy Prices homepage widget.

Source: https://www.zera.co.zw/

ZERA's homepage hosts a "Current Energy Prices" Elementor widget that
exposes the latest regulated pump prices for Petrol Blend (E20),
Diesel (D50), Electricity, and LPG, in both USD and ZWG. A sibling
"As Of: DD-MM-YYYY" sub-heading dates the snapshot.

We capture the USD prices for Petrol/Diesel (Per Litre) and LPG (Per Kg).
The site does not expose a historical archive, so each scrape contributes
one snapshot — the collect pipeline dedupes against the existing CSV.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://www.zera.co.zw/"
_COUNTRY = "Zimbabwe"
_CURRENCY = "USD"
_SOURCE_KEY = "zera_zw_current"

_AS_OF_RE = re.compile(r"As\s*Of:\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})", re.IGNORECASE)
_USD_PERIOD_RE = re.compile(r"USD\s+Per\s+(Litre|Kg)", re.IGNORECASE)

_PRODUCT_UNIT = {
    "Petrol Blend (E20)": ("Litre", "L"),
    "Diesel (D50)": ("Litre", "L"),
    "LPG": ("Kg", "kg"),
}


def _parse_as_of(soup: BeautifulSoup) -> date | None:
    m = _AS_OF_RE.search(soup.get_text(" ", strip=True))
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _extract_prices(soup: BeautifulSoup) -> dict[str, float]:
    """Walk price-table widgets, pairing each heading with the next USD value."""
    out: dict[str, float] = {}
    current_product: str | None = None
    for table in soup.select("div.bdt-price-table"):
        heading = table.select_one(".bdt-price-table-heading")
        if heading is not None:
            current_product = heading.get_text(strip=True)
        if current_product not in _PRODUCT_UNIT or current_product in out:
            continue
        period = table.select_one(".bdt-price-table-period")
        integer = table.select_one(".bdt-price-table-integer-part")
        if period is None or integer is None:
            continue
        m_period = _USD_PERIOD_RE.search(period.get_text(" ", strip=True))
        if not m_period:
            continue
        expected_unit, _ = _PRODUCT_UNIT[current_product]
        if m_period.group(1).lower() != expected_unit.lower():
            continue
        raw = integer.get_text(strip=True).replace(",", "")
        try:
            out[current_product] = float(raw)
        except ValueError:
            continue
    return out


def fetch_zera_zw(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    obs_date = _parse_as_of(soup)
    if obs_date is None:
        logger.warning("[zera_zw] no 'As Of' date found on homepage")
        return None
    if obs_date <= cutoff:
        logger.info(
            "[zera_zw] homepage date %s <= cutoff %s — skipping", obs_date, cutoff
        )
        return None

    prices = _extract_prices(soup)
    if not prices:
        logger.warning("[zera_zw] no USD prices parsed for date %s", obs_date)
        return None

    rows = []
    for product, value in prices.items():
        _, unit = _PRODUCT_UNIT[product]
        rows.append(
            {
                "observation_date": obs_date.isoformat(),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": round(value, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": unit,
            }
        )
    logger.info("[zera_zw] %s → %d products", obs_date, len(rows))
    return pd.DataFrame(rows)


__all__ = ["fetch_zera_zw"]
