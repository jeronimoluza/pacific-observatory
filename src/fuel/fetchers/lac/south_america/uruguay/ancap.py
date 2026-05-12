"""Uruguay ANCAP historical retail fuel prices fetcher.

Source: https://www.ancap.com.uy/10564/1/historico-precios-combustibles.html

ANCAP (the state oil company and price regulator) publishes its full
historical price archive as two inline HTML tables on a single page:

  Current table:    01/07/2021 → present
                    Fecha | Super 95-30S | Premium 97 30S | Gasoil 50S |
                    Gasoil 10S | Queroseno | Supergás
  Historical table: 1974 → 08/06/2021
                    Fecha | Super 95-30S | Especial 87 SP | Premium 97 30S |
                    Gasoil | Gasoil 50-S | Gasoil 10-S | Queroseno | Supergás

Format: DD/MM/YYYY dates, comma decimal ("65,47"), pre-1993 rows use a
space as thousand separator ("1 200,00") because Uruguay redenominated
the peso. Empty cells indicate a product wasn't offered at that date.

Prices: liquids in UYU/litre, Supergás in UYU/kg (residential cylinder).
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

_URL = "https://www.ancap.com.uy/10564/1/historico-precios-combustibles.html"
_COUNTRY = "Uruguay"
_CURRENCY = "UYU"
_SOURCE_KEY = "uy_ancap_historical"

# Map raw header text (lowercased, whitespace-collapsed) → canonical product name
# used in fuel_product column and YAML products: keys.
_HEADER_MAP = {
    "super 95-30s": "Super 95",
    "super 95- 30-s": "Super 95",
    "premium 97 30s": "Premium 97",
    "premium 97 30-s": "Premium 97",
    "especial 87 sp": "Especial 87",
    "gasoil": "Gasoil",
    "gasoil 50s": "Gasoil 50S",
    "gasoil 50-s": "Gasoil 50S",
    "gasoil 10s": "Gasoil 10S",
    "gasoil 10-s": "Gasoil 10S",
    "queroseno": "Queroseno",
    "supergás": "Supergas",
    "supergas": "Supergas",
}

_PRODUCT_UNITS = {
    "Super 95": "L",
    "Premium 97": "L",
    "Especial 87": "L",
    "Gasoil": "L",
    "Gasoil 50S": "L",
    "Gasoil 10S": "L",
    "Queroseno": "L",
    "Supergas": "kg",
}

_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_price(value: str) -> float | None:
    text = _normalize(value)
    if not text:
        return None
    # Uruguay: comma decimal, space (or period) as thousand separator
    text = text.replace(" ", "").replace(".", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned or cleaned in {".", "-"}:
        return None
    try:
        price = float(cleaned)
    except ValueError:
        return None
    if price <= 0:
        return None
    return price


def _parse_date(value: str) -> date | None:
    match = _DATE_RE.search(_normalize(value))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_table(table) -> list[tuple[date, str, float]]:
    rows = table.find_all("tr")
    if not rows:
        return []

    header_cells = [
        _normalize(c.get_text(" ", strip=True)).lower()
        for c in rows[0].find_all(["td", "th"])
    ]
    # Column 0 is "Fecha"; map remaining columns to canonical product names.
    product_by_col: dict[int, str] = {}
    for idx, head in enumerate(header_cells):
        if idx == 0:
            continue
        canonical = _HEADER_MAP.get(head)
        if canonical is not None:
            product_by_col[idx] = canonical

    if not product_by_col:
        return []

    out: list[tuple[date, str, float]] = []
    for row in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not cells:
            continue
        obs_date = _parse_date(cells[0])
        if obs_date is None:
            continue
        for col, product in product_by_col.items():
            if col >= len(cells):
                continue
            price = _parse_price(cells[col])
            if price is None:
                continue
            out.append((obs_date, product, price))
    return out


def fetch_uy_ancap(cutoff: date) -> pd.DataFrame | None:
    """Fetch Uruguay ANCAP retail fuel prices (UYU/L; LPG in UYU/kg)."""
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[uy_ancap] Failed to fetch ANCAP page")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    events: list[tuple[date, str, float]] = []
    for table in soup.find_all("table"):
        events.extend(_parse_table(table))

    if not events:
        logger.warning("[uy_ancap] No price events parsed")
        return None

    # Deduplicate (date, product) — keep first occurrence (current table wins on overlap).
    seen: set[tuple[date, str]] = set()
    rows: list[dict] = []
    for obs_date, product, price in events:
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
        logger.info("[uy_ancap] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[uy_ancap] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
