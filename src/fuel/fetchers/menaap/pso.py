"""PSO Pakistan fuel price fetcher — paginated HTML archive scraping.

Scraping strategy:
  Iterate archive pages (newest-first) at psopk.com/fuel-prices/pol/archives
  Parse UIkit accordion entries: date header + table rows per entry
  Stop when all entries on a page predate the cutoff

Products tracked: Premier Euro 5, Hi-Cetane Diesel Euro 5, LDO, SKO, JP-1,
E10 Gasoline (historical data 2010–2022, Rs.0 after Aug 2022).
Rows with "--" or empty prices are silently skipped (product not available).
"""

import logging
import re
import time
from datetime import date, datetime

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://psopk.com/fuel-prices/pol/archives"
_COUNTRY = "Pakistan"
_CURRENCY = "PKR"
_SOURCE_KEY = "pso_pk_biweekly"

_DATE_RE = re.compile(r"Effective From:\s*(.+?)(?:\s*$)")
_PRICE_RE = re.compile(r"Rs\.([\d,]+\.?\d*)/Ltr")


def _parse_page(html: str, cutoff: date) -> tuple[list[dict], bool]:
    """Parse one archive page, return (rows, should_continue).

    should_continue is False when ALL entries on the page are at or before cutoff.
    """
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("ul[uk-accordion] > li")
    if not items:
        return [], False

    rows: list[dict] = []
    found_after_cutoff = False

    for item in items:
        title_el = item.select_one("a.uk-accordion-title")
        if not title_el:
            continue

        title_text = title_el.get_text(strip=True)
        m = _DATE_RE.search(title_text)
        if not m:
            logger.warning("[pso_pk] unparseable date header: %s", title_text[:80])
            continue

        try:
            obs_date = datetime.strptime(m.group(1).strip(), "%B %d, %Y").date()
        except ValueError:
            logger.warning("[pso_pk] bad date format: %s", m.group(1))
            continue

        if obs_date <= cutoff:
            continue

        found_after_cutoff = True
        obs_str = obs_date.strftime("%Y-%m-%d")

        table = item.select_one("table.uk-table")
        if not table:
            logger.warning("[pso_pk] no table found for %s", obs_str)
            continue

        for tr in table.select("tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue

            product = cells[0].get_text(strip=True)
            price_text = cells[1].get_text(strip=True)

            if not price_text or price_text in ("--", "Rs./Ltr"):
                continue

            pm = _PRICE_RE.search(price_text)
            if not pm:
                logger.warning("[pso_pk] unparseable price: %s", price_text[:40])
                continue

            price = float(pm.group(1).replace(",", ""))
            if price == 0:
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


def fetch_pk_pso(cutoff: date) -> pd.DataFrame | None:
    """Fetch Pakistan fuel prices from PSO archive (paginated HTML)."""
    session = make_session()
    all_rows: list[dict] = []

    page = 1
    while True:
        url = f"{_BASE_URL}?page={page}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception:
            logger.exception("[pso_pk] failed to fetch page %d", page)
            break

        rows, should_continue = _parse_page(resp.text, cutoff)
        all_rows.extend(rows)
        logger.info("[pso_pk] page %d: %d rows extracted", page, len(rows))

        if not should_continue:
            break

        page += 1
        time.sleep(1)

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
