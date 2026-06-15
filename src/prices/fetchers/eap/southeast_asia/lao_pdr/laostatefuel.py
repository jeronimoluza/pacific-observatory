"""Lao State Fuel Company — retail pump prices by province.

Scrapes the paginated HTML table at laostatefuel.com/en/gas-price.html
(up to 294 pages of history from ~2016). Emits one PriceObservation row
per (province, fuel_type, observation_date) triple.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE_URL = "https://laostatefuel.com/en/gas-price.html"
_COUNTRY = "Lao PDR"
_CURRENCY = "LAK"
_SOURCE_KEY = "la_laostatefuel"
_UNIT = "L"

# Petrol grades → COICOP 07.2.2 (Motor fuels); diesel → 07.2.3 (Other fuels)
_COICOP_MAP = {
    "Gasoline 95": "07.2.2",
    "Gasoline 92": "07.2.2",
    "Regular": "07.2.2",
    "Diesel": "07.2.3",
}

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

# Pattern: "Province : Vientiane Capital Date\n2026-04-18   Gasoline 95 : 38,940 KIP ..."
_PROVINCE_RE = re.compile(r"Province\s*:\s*(.+?)\s+Date", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_FUEL_RE = re.compile(
    r"(Gasoline 95|Gasoline 92|Regular|Diesel)\s*:\s*([\d,]+)\s*KIP", re.IGNORECASE
)


def _parse_price(raw: str) -> float:
    return float(raw.replace(",", ""))


def _scrape_page(session: requests.Session, page: int) -> list[dict]:
    url = _BASE_URL if page == 1 else f"{_BASE_URL}/?page={page}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    rows: list[dict] = []
    for li in soup.select("li[style*='color: #fff']"):
        text = li.get_text(separator=" ", strip=True)
        province_m = _PROVINCE_RE.search(text)
        date_m = _DATE_RE.search(text)
        if not province_m or not date_m:
            continue
        province = province_m.group(1).strip()
        obs_date_str = date_m.group(1)
        try:
            date.fromisoformat(obs_date_str)
        except ValueError:
            continue

        for fuel_m in _FUEL_RE.finditer(text):
            fuel_name = fuel_m.group(1).strip()
            # Normalise "Gasoline 95" and "Regular" — site shows both for same grade
            if fuel_name.lower() == "regular":
                fuel_name = "Gasoline 92"
            coicop = _COICOP_MAP.get(fuel_name)
            if not coicop:
                logger.warning(
                    "No COICOP mapping for fuel %r — dropping row", fuel_name
                )
                continue
            row: dict = {
                "observation_date": obs_date_str,
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "subnational_area": province,
                "item_name": fuel_name,
                "price_local": _parse_price(fuel_m.group(2)),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "coicop_code": coicop,
                "source_url": url,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def _total_pages(session: requests.Session) -> int:
    resp = session.get(_BASE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    pagination = soup.select("ul.pagination li a")
    page_nums = []
    for a in pagination:
        try:
            page_nums.append(int(a.get_text(strip=True)))
        except ValueError:
            pass
    return max(page_nums) if page_nums else 1


def fetch_la_laostatefuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    all_rows: list[dict] = []
    total = _total_pages(session)
    # Iterate from newest (page 1) to oldest, stopping when all rows on a page
    # are before the cutoff.
    for page in range(1, total + 1):
        page_rows = _scrape_page(session, page)
        new_rows = [
            r for r in page_rows if date.fromisoformat(r["observation_date"]) > cutoff
        ]
        all_rows.extend(new_rows)
        # If every row on this page is at or before the cutoff, stop paginating.
        if page_rows and not new_rows:
            break
    return pd.DataFrame(all_rows) if all_rows else None
