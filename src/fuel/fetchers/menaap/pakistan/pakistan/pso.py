"""PSO Pakistan fuel price fetcher: paginated HTML archive scraping."""

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
    """Parse one archive page, returning rows and whether to continue paging."""
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

        match = _DATE_RE.search(title_el.get_text(strip=True))
        if not match:
            logger.warning(
                "[pso_pk] unparseable date header: %s",
                title_el.get_text(strip=True)[:80],
            )
            continue

        try:
            observation_date = datetime.strptime(
                match.group(1).strip(), "%B %d, %Y"
            ).date()
        except ValueError:
            logger.warning("[pso_pk] bad date format: %s", match.group(1))
            continue

        if observation_date <= cutoff:
            continue

        found_after_cutoff = True
        obs_str = observation_date.strftime("%Y-%m-%d")

        table = item.select_one("table.uk-table")
        if not table:
            logger.warning("[pso_pk] no table found for %s", obs_str)
            continue

        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            product = cells[0].get_text(strip=True)
            price_text = cells[1].get_text(strip=True)
            if not price_text or price_text in {"--", "Rs./Ltr"}:
                continue

            price_match = _PRICE_RE.search(price_text)
            if not price_match:
                logger.warning("[pso_pk] unparseable price: %s", price_text[:40])
                continue

            price = float(price_match.group(1).replace(",", ""))
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
    """Fetch Pakistan fuel prices from the PSO archive."""
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
