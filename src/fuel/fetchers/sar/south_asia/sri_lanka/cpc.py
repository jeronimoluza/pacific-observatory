"""Ceylon Petroleum Corporation historical fuel prices: single-page HTML table."""

import logging
from datetime import date, datetime

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://ceypetco.gov.lk/historical-prices/"
_COUNTRY = "Sri Lanka"
_CURRENCY = "LKR"
_SOURCE_KEY = "cpc_lk_historical"

_HEADER_TO_PRODUCT = {
    "LP 95": "LP 95",
    "LP 92": "LP 92",
    "LAD": "LAD",
    "LSD": "LSD",
    "LK": "LK",
    "LIK": "LIK",
}


def _normalize_header(text: str) -> str:
    return " ".join(text.split()).upper()


def _parse_table(html: str, cutoff: date) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []

    header_cells = [
        _normalize_header(th.get_text(" ", strip=True)) for th in table.find_all("th")
    ]
    col_to_product: dict[int, str] = {}
    for i, h in enumerate(header_cells):
        for key, product in _HEADER_TO_PRODUCT.items():
            if h == _normalize_header(key):
                col_to_product[i] = product
                break

    if not col_to_product:
        logger.warning(
            "[cpc_lk] no recognised product columns in header: %s", header_cells
        )
        return []

    rows: list[dict] = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        date_text = cells[0].get_text(" ", strip=True)
        try:
            observation_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        except ValueError:
            logger.debug("[cpc_lk] skipping non-date row: %s", date_text[:60])
            continue

        if observation_date <= cutoff:
            continue
        obs_str = observation_date.strftime("%Y-%m-%d")

        for col_idx, product in col_to_product.items():
            if col_idx >= len(cells):
                continue
            price_text = cells[col_idx].get_text(strip=True).replace(",", "")
            if not price_text or price_text in {"-", "—", "N/A"}:
                continue
            try:
                price = float(price_text)
            except ValueError:
                logger.warning(
                    "[cpc_lk] unparseable price (%s): %s", product, price_text
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

    return rows


def fetch_lk_cpc(cutoff: date) -> pd.DataFrame | None:
    """Fetch Sri Lanka historical fuel prices from CPC."""
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[cpc_lk] failed to fetch %s", _URL)
        return None

    rows = _parse_table(resp.text, cutoff)
    logger.info("[cpc_lk] %d rows extracted", len(rows))
    if not rows:
        return None

    return pd.DataFrame(rows)
