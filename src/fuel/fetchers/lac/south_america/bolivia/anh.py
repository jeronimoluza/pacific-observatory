"""Bolivia ANH monthly "Precios Internacionales" fetcher.

Source: Agencia Nacional de Hidrocarburos.
URL:    https://www.anh.gob.bo/w2019/contenido.php?s=13&Y={YYYY}

Bolivia runs a dual fuel-pricing regime:
  - Mercado interno (Bolivian plates): heavily subsidized, frozen since 2005
    (Gasolina Especial Bs 3.74/L, Diesel Bs 3.72/L). Image-only on the site.
  - Precios Internacionales (foreign plates / aviation / industry): set
    monthly by ANH via resolución administrativa. These adjust with market
    conditions and ARE published as structured HTML tables per year.

Per-year HTML pages expose one <h3> + <table> per month covering:
  Gasolina Especial Internacional   (Bs/l)
  Diesel Oil Internacional          (Bs/l)
  Gas Natural Vehicular Internacional (Bs/m³)
  Jet Fuel Internacional            (Bs/l)
  Gasolina Especial + Internacional (Bs/l)

Structured tables exist from 2020 onwards (earlier years show only an
aggregate PNG). Each row gives VIGENTE A PARTIR DE (effective date) and
PRECIO FINAL; multi-date cells indicate two adjustments within the month.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.anh.gob.bo/w2019/contenido.php?s=13&Y={year}"
_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")

_COUNTRY = "Bolivia"
_CURRENCY = "BOB"
_SOURCE_KEY = "bo_anh_monthly"
_FIRST_YEAR = 2020
_REQUEST_DELAY_S = 1.0

_PRODUCTS = {
    "Gasolina Especial Internacional": "L",
    "Diesel Oil Internacional": "L",
    "Gas Natural Vehicular Internacional": "M3",
    "Jet Fuel Internacional": "L",
    "Gasolina Especial + Internacional": "L",
}


def _parse_number(token: str) -> float | None:
    text = token.strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_dates(cell: str) -> list[date]:
    out: list[date] = []
    for d, m, y in _DATE_RE.findall(cell):
        try:
            out.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return out


def _extract_prices(cell: str) -> list[float]:
    out: list[float] = []
    for tok in _NUMBER_RE.findall(cell):
        v = _parse_number(tok)
        if v is not None:
            out.append(v)
    return out


def _parse_year(html: str, year: int) -> list[dict]:
    """Parse the 'PRECIOS INTERNACIONALES <year>' section into rows."""
    soup = BeautifulSoup(html, "html.parser")
    header_text = f"PRECIOS INTERNACIONALES {year}"
    section_header = next(
        (h for h in soup.find_all("h3") if h.get_text(strip=True) == header_text),
        None,
    )
    if section_header is None:
        return []

    rows: list[dict] = []
    current_month: int | None = None
    for cur in section_header.find_all_next():
        if cur.name == "h3":
            text = cur.get_text(strip=True)
            if text.startswith("PRECIOS ") and text != header_text:
                # Hit the next top-level section — stop.
                break
            current_month = _month_number(text)
        elif cur.name == "table" and current_month is not None:
            rows.extend(_parse_table(cur, year, current_month))
    return rows


_MONTH_NAMES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _month_number(label: str) -> int | None:
    label = label.lower()
    for name, num in _MONTH_NAMES.items():
        if name in label:
            return num
    return None


def _parse_table(table, year: int, month: int) -> list[dict]:
    out: list[dict] = []
    trs = table.find_all("tr")
    if len(trs) < 2:
        return out
    for tr in trs[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        product = cells[0].strip()
        vigente_cell = cells[2]
        precio_cell = cells[3]

        if product not in _PRODUCTS:
            continue

        dates = _extract_dates(vigente_cell)
        prices = _extract_prices(precio_cell)
        if not prices:
            continue
        if not dates:
            # "A partir de su publicación" — fall back to month-start.
            try:
                dates = [date(year, month, 1)]
            except ValueError:
                continue

        unit = _PRODUCTS[product]
        for i, eff_date in enumerate(dates):
            price = prices[i] if i < len(prices) else prices[-1]
            if price <= 0:
                continue
            out.append(
                {
                    "observation_date": eff_date.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": unit,
                }
            )
    return out


def fetch_bo_anh(cutoff: date) -> pd.DataFrame | None:
    """Fetch Bolivia ANH 'Precios Internacionales' monthly retail prices (Bs/l, Bs/m³)."""
    today = datetime.now(timezone.utc).date()
    session = make_session()

    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []

    start_year = max(_FIRST_YEAR, cutoff.year)
    for year in range(start_year, today.year + 1):
        url = _PAGE_URL.format(year=year)
        try:
            resp = session.get(url, timeout=45)
            resp.raise_for_status()
        except Exception:
            logger.warning("[bo_anh] Failed to fetch %s", url)
            time.sleep(_REQUEST_DELAY_S)
            continue
        year_rows = _parse_year(resp.text, year)
        added = 0
        for row in year_rows:
            obs_date = datetime.strptime(row["observation_date"], "%Y-%m-%d").date()
            if obs_date <= cutoff:
                continue
            key = (row["observation_date"], row["fuel_product"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            added += 1
        logger.info("[bo_anh] %d → %d new rows", year, added)
        time.sleep(_REQUEST_DELAY_S)

    if not rows:
        logger.info("[bo_anh] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[bo_anh] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
