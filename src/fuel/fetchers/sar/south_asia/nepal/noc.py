"""Nepal Oil Corporation retail price archive: paginated HTML table scraping."""

import logging
import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://noc.org.np/retailprice"
_COUNTRY = "Nepal"
_CURRENCY = "NPR"
_SOURCE_KEY = "noc_np_retail"
_PAGE_SIZE = 10

_DATE_TOKEN_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_PRODUCT_COLS = {
    2: "Petrol",
    3: "Diesel",
    4: "Kerosene",
}


def _extract_ad_date(date_text: str) -> date | None:
    """Pick the Gregorian (AD) date out of a NOC cell, ignoring the BS one.

    NOC inconsistently writes either ``BS (AD)`` or ``AD (BS)`` and uses BS
    years 2050-2099 vs AD years 2000-2049, so disambiguate by year range.
    """
    for y, m, d in _DATE_TOKEN_RE.findall(date_text):
        year = int(y)
        if 2000 <= year < 2050:
            try:
                return date(year, int(m), int(d))
            except ValueError:
                continue
    return None


def _parse_page(html: str, cutoff: date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return [], False

    rows: list[dict] = []
    found_after_cutoff = False

    body_rows = table.find_all("tr")[1:]
    for tr in body_rows:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 5:
            continue

        date_text = cells[0].get_text(" ", strip=True)
        observation_date = _extract_ad_date(date_text)
        if not observation_date:
            logger.warning("[noc_np] no AD date in: %s", date_text[:80])
            continue

        if observation_date > date.today():
            logger.warning(
                "[noc_np] dropping future-dated row (likely typo): %s", date_text
            )
            continue

        if observation_date <= cutoff:
            continue
        found_after_cutoff = True
        obs_str = observation_date.strftime("%Y-%m-%d")

        for col_idx, product in _PRODUCT_COLS.items():
            if col_idx >= len(cells):
                continue
            price_text = cells[col_idx].get_text(strip=True).replace(",", "")
            if not price_text or price_text == "-":
                continue
            try:
                price = float(price_text)
            except ValueError:
                logger.warning(
                    "[noc_np] unparseable price for %s: %s", product, price_text
                )
                continue
            if price <= 0:
                continue
            rows.append(
                {
                    "observation_date": obs_str,
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )

    return rows, found_after_cutoff


def fetch_np_noc(cutoff: date) -> pd.DataFrame | None:
    """Fetch Nepal retail fuel prices from the NOC archive."""
    session = make_session()
    all_rows: list[dict] = []

    offset = 0
    while True:
        url = f"{_BASE_URL}?offset={offset}&max={_PAGE_SIZE}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception:
            logger.exception("[noc_np] failed to fetch offset %d", offset)
            break

        rows, should_continue = _parse_page(resp.text, cutoff)
        all_rows.extend(rows)
        logger.info("[noc_np] offset %d: %d rows extracted", offset, len(rows))

        if not should_continue:
            break

        offset += _PAGE_SIZE
        time.sleep(1)

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
