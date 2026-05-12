"""Bangladesh Petroleum Corporation retail price page (live + Wayback)."""

import logging
import re
from datetime import date, datetime

import pandas as pd
import urllib3
from bs4 import BeautifulSoup

from core.http import make_session
from fuel.fetchers._shared.sar.wayback import iterate_snapshots

logger = logging.getLogger(__name__)

# BPC's TLS chain is missing intermediates on some networks — silence the warning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_URL = "https://bpc.gov.bd/pages/static-pages/6922ddb6933eb65569e15fbc"
_COUNTRY = "Bangladesh"
_CURRENCY = "BDT"
_SOURCE_KEY = "bpc_bd_retail"

# Bengali → ASCII digit map
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Bengali product names → canonical English label
_PRODUCTS_BN = {
    "ডিজেল": "Diesel",
    "কেরোসিন": "Kerosene",
    "অকটেন": "Octane",
    "পেট্রোল": "Petrol",
}


def _bn_to_ascii(text: str) -> str:
    return text.translate(_BN_DIGITS)


def _parse_date(text: str) -> date | None:
    """Parse a BPC date cell (Bengali DD/MM/YYYY) into a Gregorian date."""
    ascii_text = _bn_to_ascii(text).strip()
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", ascii_text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(0), "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_price(text: str) -> float | None:
    """Extract a numeric price from a BPC price cell (e.g. '১১৫.০০ (টাকা/লিটার)')."""
    ascii_text = _bn_to_ascii(text)
    m = re.search(r"(\d+(?:\.\d+)?)", ascii_text)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_table(html: str) -> list[dict]:
    """Extract rows from the BPC primary product table."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []

    rows: list[dict] = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 4:
            continue

        product_bn = cells[1].get_text(" ", strip=True)
        product = _PRODUCTS_BN.get(product_bn)
        if not product:
            continue

        price = _parse_price(cells[2].get_text(" ", strip=True))
        if price is None:
            continue

        observation_date = _parse_date(cells[3].get_text(" ", strip=True))
        if observation_date is None:
            continue

        rows.append(
            {
                "observation_date": observation_date.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": price,
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "L",
            }
        )
    return rows


def _fetch_live() -> list[dict]:
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("[bpc_bd] live fetch failed")
        return []
    return _parse_table(resp.text)


def fetch_bd_bpc(cutoff: date) -> pd.DataFrame | None:
    """Fetch Bangladesh BPC retail prices (Wayback backfill + live current)."""
    seen: set[tuple[str, str]] = set()
    all_rows: list[dict] = []

    for snap_date, html in iterate_snapshots(_URL, cutoff, collapse_digits=6):
        for row in _parse_table(html):
            obs = row["observation_date"]
            if datetime.strptime(obs, "%Y-%m-%d").date() <= cutoff:
                continue
            key = (obs, row["fuel_product"])
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)

    for row in _fetch_live():
        obs = row["observation_date"]
        if datetime.strptime(obs, "%Y-%m-%d").date() <= cutoff:
            continue
        key = (obs, row["fuel_product"])
        if key in seen:
            continue
        seen.add(key)
        all_rows.append(row)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
