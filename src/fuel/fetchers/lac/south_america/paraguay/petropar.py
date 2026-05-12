"""Paraguay PETROPAR current retail fuel prices fetcher.

Source: https://www.petropar.gov.py/?page_id=4460

PETROPAR (Petróleos Paraguayos, state oil company) publishes its current
retail prices as a single inline HTML table on its public website:

  Producto                | Precio    | Vigencia
  Diésel Porã             | G. 8.200  | 04/05/2026
  Diésel Mbarete          | G. 10.000 | 04/05/2026
  Nafta Kape 88           | G. 6.690  | 04/05/2026
  Nafta Oikoite 93        | G. 7.190  | 04/05/2026
  Nafta Aratiri 97        | G. 8.540  | 04/05/2026
  Ñande Gas por Kilogramo | G. 7.374  | 23/05/2025
  Ñande Gas por Litro     | G. 4.240  | 23/05/2025

The page only exposes the *current* effective prices — there is no
public historical table. Each row carries its own "Vigencia" (effective-
from) date, so the fetcher emits one row per product dated by that
vigencia. Subsequent fetches return the same rows until PETROPAR posts
a new price.

Prices in PYG: "G. 8.200" uses '.' as the thousand separator (=8200 PYG).
Liquid fuels are per litre; Ñande Gas (LPG) is listed both per kg and per L.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://www.petropar.gov.py/?page_id=4460"
_COUNTRY = "Paraguay"
_CURRENCY = "PYG"
_SOURCE_KEY = "py_petropar_current"

_PRODUCT_UNITS = {
    "Nafta Kape 88": "L",
    "Nafta Oikoite 93": "L",
    "Nafta Aratiri 97": "L",
    "Diésel Porã": "L",
    "Diésel Mbarete": "L",
    "Ñande Gas por Kilogramo": "kg",
    "Ñande Gas por Litro": "L",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_price(value: str) -> float | None:
    text = _normalize(value).replace("G.", "").strip()
    # PYG amounts use '.' as thousand separator. There are no decimals
    # in the published values (whole guaraníes).
    text = text.replace(".", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        return None
    try:
        price = float(cleaned)
    except ValueError:
        return None
    return price if price > 0 else None


def _parse_date(value: str) -> date | None:
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", _normalize(value))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%d/%m/%Y").date()
    except ValueError:
        return None


def fetch_py_petropar(cutoff: date) -> pd.DataFrame | None:
    """Fetch Paraguay PETROPAR current retail fuel prices (PYG/L; PYG/kg for LPG)."""
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[py_petropar] Failed to fetch PETROPAR page")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    rows: list[dict] = []
    seen: set[tuple[date, str]] = set()
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            product = _normalize(cells[0])
            if product not in _PRODUCT_UNITS:
                continue
            price = _parse_price(cells[1])
            obs_date = _parse_date(cells[2])
            if price is None or obs_date is None:
                continue
            if obs_date <= cutoff:
                continue
            key = (obs_date, product)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": _PRODUCT_UNITS[product],
                }
            )

    if not rows:
        logger.info("[py_petropar] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[py_petropar] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
