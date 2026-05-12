"""Colombia CREG retail liquid fuels (gasoline + ACPM) fetcher.

Source: https://creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos/

CREG publishes the historical archive of regulated retail prices as inline
HTML tables — one table per price-change event, dating from March 2022
through the present. Each event lists 13-18 main Colombian cities with:

  No. | Ciudad | Gasolina MC ($/gal) | ACPM ($/gal)

Prices are in COP/gallon (Colombian thousand-separator: "16.291" = 16291).
We pair each table with the most recent "vigencia / partir del" date heading
in DOM order, dedupe by date, and emit the national mean per product.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos/"
_COUNTRY = "Colombia"
_CURRENCY = "COP"
_SOURCE_KEY = "co_creg_liquids"

_SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_DATE_RE = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:de\s*l?\s*)?(\d{4})",
    re.IGNORECASE,
)
_DATE_TRIGGER_RE = re.compile(
    r"(vigent|partir\s+del|vigencia|referencia)",
    re.IGNORECASE,
)

_PRODUCT_COLS = {
    "GASOLINA MC": 2,  # 3rd column (0-indexed): Gasolina MC ($/gal)
    "ACPM": 3,  # 4th column: ACPM ($/gal)
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_spanish_date(text: str) -> date | None:
    text = _normalize(text).lower()
    match = _DATE_RE.search(text)
    if not match:
        return None
    month = _SPANISH_MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None


def _parse_price(value: str) -> float | None:
    text = _normalize(value).replace(".", "").replace(",", ".")
    # Some cells contain stray characters (typos like "11/.016"); keep digits + dot
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned or cleaned == ".":
        return None
    try:
        price = float(cleaned)
    except ValueError:
        return None
    if price <= 0:
        return None
    return price


def _extract_events(html: str) -> list[tuple[date, str, float]]:
    """Yield (effective_date, product, national_mean_price) tuples."""
    soup = BeautifulSoup(html, "html.parser")
    elements = soup.find_all(
        ["table", "p", "h2", "h3", "h4", "h5", "strong", "div", "span"]
    )

    seen_dates: set[date] = set()
    current_date: date | None = None
    events: list[tuple[date, str, float]] = []

    for el in elements:
        if el.name != "table":
            text = el.get_text(" ", strip=True)
            if text and _DATE_TRIGGER_RE.search(text):
                parsed = _parse_spanish_date(text)
                if parsed is not None:
                    current_date = parsed
            continue

        if current_date is None or current_date in seen_dates:
            if current_date is not None:
                seen_dates.add(current_date)
            continue

        prices_by_product: dict[str, list[float]] = {p: [] for p in _PRODUCT_COLS}
        for row in el.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            # Skip header rows
            first = _normalize(cells[0]).lower()
            if not first.isdigit():
                continue
            for product, col in _PRODUCT_COLS.items():
                if col >= len(cells):
                    continue
                price = _parse_price(cells[col])
                if price is None:
                    continue
                prices_by_product[product].append(price)

        for product, values in prices_by_product.items():
            if not values:
                continue
            mean = sum(values) / len(values)
            events.append((current_date, product, mean))

        seen_dates.add(current_date)

    return events


def fetch_co_creg(cutoff: date) -> pd.DataFrame | None:
    """Fetch Colombia CREG retail gasoline + ACPM prices (COP/gallon)."""
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[co_creg] Failed to fetch CREG page")
        return None

    events = _extract_events(resp.text)
    if not events:
        logger.warning("[co_creg] No price events parsed")
        return None

    rows: list[dict] = []
    for obs_date, product, price in events:
        if obs_date <= cutoff:
            continue
        rows.append(
            {
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "gal",
            }
        )

    if not rows:
        logger.info("[co_creg] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[co_creg] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
