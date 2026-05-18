"""Uzbekistan — goldenpages.uz Tashkent gas-station prices.

Source pages:
  - https://www.goldenpages.uz/en/benzin-cena/ — current year, multiple
    "as of <date>" sections each followed by a station × product table.
  - https://www.goldenpages.uz/en/benzin-cena/archiv-benzin/<YYYY>/ —
    per-year archive, available from 2020 onwards (earlier years are
    mentioned in metadata but return 404). Older archives label dates in
    Russian (``по состоянию на 29 декабря 2020 г.``); 2025+ uses English
    (``as of May 12, 2026``).

The table headers are: ``Gas station name | AI-80 | AI-92 UZB | AI-92 IMPORT
| AI-95 | AI-98 | AI-100 | Diesel``. Prices missing for a station are ``-``;
values are space-separated thousands in soum per litre (e.g. ``10 800``).
"""

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup, Tag

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE = "https://www.goldenpages.uz/en/benzin-cena/"
_ARCHIVE_TMPL = _BASE + "archiv-benzin/{year}/"
_COUNTRY = "Uzbekistan"
_CITY = "Tashkent"
_CURRENCY = "UZS"
_SOURCE_KEY = "uz_goldenpages_biweekly"

_EN_DATE_RE = re.compile(
    r"as\s+of\s+([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", re.IGNORECASE
)
_RU_DATE_RE = re.compile(
    r"по\s+состоянию\s+на\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})", re.IGNORECASE
)

_EN_MONTHS = {
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
}
_RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

# Map raw column headers (as scraped) to canonical product names.
_PRODUCT_MAP = {
    "AI-80": "AI-80",
    "AI-92 UZB": "AI-92 UZB",
    "AI-92 IMPORT": "AI-92 IMPORT",
    "AI-95": "AI-95",
    "AI-98": "AI-98",
    "AI-100": "AI-100",
    "Diesel": "Diesel",
}

# Earliest accessible archive year (older URLs 404).
_FIRST_ARCHIVE_YEAR = 2020


def _parse_price(raw: str) -> float | None:
    """Convert ``'10 800'`` → 10800.0; return None for ``'-'`` or junk."""
    s = raw.replace("\xa0", " ").strip()
    if not s or s in {"-", "—", "–"}:
        return None
    s = s.replace(" ", "").replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


def _find_date_near(table: Tag) -> date | None:
    """Walk back from ``table`` looking for the nearest "as of" / "по состоянию на" header."""
    cur: Tag | None = table
    for _ in range(40):
        cur = cur.find_previous(
            ["h2", "h3", "h4", "h5", "h6", "p", "div", "strong", "b", "span"]
        )
        if cur is None:
            return None
        text = cur.get_text(" ", strip=True)
        m = _EN_DATE_RE.search(text)
        if m:
            month = _EN_MONTHS.get(m.group(1).lower())
            if month:
                try:
                    return date(int(m.group(3)), month, int(m.group(2)))
                except ValueError:
                    pass
        m = _RU_DATE_RE.search(text)
        if m:
            month = _RU_MONTHS.get(m.group(2).lower())
            if month:
                try:
                    return date(int(m.group(3)), month, int(m.group(1)))
                except ValueError:
                    pass
    return None


def _parse_year_html(html: str, cutoff: date) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for table in soup.find_all("table", class_="petrol_price_table"):
        obs = _find_date_near(table)
        if obs is None:
            continue
        if obs <= cutoff:
            continue
        tr_list = table.find_all("tr")
        if not tr_list:
            continue
        headers = [
            th.get_text(" ", strip=True) for th in tr_list[0].find_all(["th", "td"])
        ]
        # Map header text → column index (skip "Gas station name" / unknowns).
        product_cols: dict[str, int] = {}
        for idx, h in enumerate(headers):
            product = _PRODUCT_MAP.get(h)
            if product:
                product_cols[product] = idx
        if not product_cols:
            continue
        for tr in tr_list[1:]:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            station = cells[0]
            if not station:
                continue
            for product, col_idx in product_cols.items():
                if col_idx >= len(cells):
                    continue
                price = _parse_price(cells[col_idx])
                if price is None:
                    continue
                rows.append(
                    {
                        "observation_date": obs.isoformat(),
                        "country": _COUNTRY,
                        "fuel_product": product,
                        "price_local": price,
                        "currency": _CURRENCY,
                        "source_key": _SOURCE_KEY,
                        "unit": "L",
                        "city": _CITY,
                        "address": station,
                    }
                )
    return rows


def fetch_uz_goldenpages(cutoff: date) -> pd.DataFrame | None:
    """Fetch Uzbekistan (Tashkent) gas-station prices from goldenpages.uz."""
    session = make_session()
    today = date.today()

    urls: list[str] = [_BASE]
    start_year = max(_FIRST_ARCHIVE_YEAR, cutoff.year)
    for year in range(start_year, today.year):
        urls.append(_ARCHIVE_TMPL.format(year=year))

    all_rows: list[dict] = []
    for url in urls:
        try:
            resp = session.get(url, timeout=60)
        except Exception:
            logger.exception("[uz_goldenpages] request failed: %s", url)
            continue
        if resp.status_code == 404:
            logger.debug("[uz_goldenpages] 404 for %s", url)
            continue
        if not resp.ok:
            logger.warning("[uz_goldenpages] HTTP %s for %s", resp.status_code, url)
            continue
        all_rows.extend(_parse_year_html(resp.text, cutoff))

    if not all_rows:
        return None

    # De-dupe in case the current page overlaps an archive year.
    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(
        subset=["observation_date", "fuel_product", "address"], keep="first"
    )
    return df.reset_index(drop=True)
