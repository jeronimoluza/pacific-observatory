"""Cathay Pharmacy Macau common-use product catalog."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, make_hash

_BASE = "https://cathaypharmacy.com/"
_LIST_URL = urljoin(_BASE, "products.php")
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_cathay_pharmacy_common"
_IDENT = ["source_key", "observation_date", "item_name", "source_url"]
_MAX_PAGES_PER_CATEGORY = 40

_CATEGORIES = {
    "health_food": "health_food",
    "medical_device": "medical_device",
    "personal_care": "personal_care",
    "feminine_care": "feminine_care",
    "milk": "milk",
    "diaper": "diaper",
    "baby_care": "baby_care",
    "paper": "paper",
    "household": "household",
    "daily": "daily",
}

_PRICE_RE = re.compile(r"[\d,.]+")


def _clean_product_url(href: str) -> str:
    url = urljoin(_BASE, href)
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    match = _PRICE_RE.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _rows_from_page(html_text: str, category: str, today: date) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    rows: list[dict] = []
    scrape_ts = get_scrape_ts()

    for card in soup.select("#productList a.product"):
        name_el = card.select_one(".p-name")
        href = card.get("href")
        if not name_el or not href:
            continue
        name = name_el.get_text(" ", strip=True)
        price_el = card.select_one(".sale-price-badge__amount") or card.select_one(
            ".p-price-main"
        )
        price = _parse_price(price_el.get_text(" ", strip=True) if price_el else None)
        if not name or price is None:
            continue

        brand_el = card.select_one(".p-sub")
        brand = brand_el.get_text(" ", strip=True) if brand_el else None
        notes = f"category={category}"
        if brand:
            notes = f"{notes}; {brand}"

        row = {
            "observation_date": today.isoformat(),
            "period_kind": "current",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": name[:500],
            "price_local": price,
            "currency": _CURRENCY,
            "unit": None,
            "source_url": _clean_product_url(href),
            "notes": notes,
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return rows


def fetch_mo_cathay_pharmacy_common(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "python-requests/2.32",
        }
    )

    all_rows: list[dict] = []
    seen_urls: set[str] = set()

    for category in _CATEGORIES:
        for page in range(1, _MAX_PAGES_PER_CATEGORY + 1):
            resp = session.get(
                _LIST_URL,
                params={"category": category, "page": page},
                timeout=45,
            )
            resp.raise_for_status()
            rows = _rows_from_page(resp.text, category, today)
            new_rows = []
            for row in rows:
                if row["source_url"] in seen_urls:
                    continue
                seen_urls.add(row["source_url"])
                new_rows.append(row)
            all_rows.extend(new_rows)

            soup = BeautifulSoup(resp.text, "html.parser")
            if not soup.select_one('link[rel="next"], .pagination a[aria-label="下一頁"]'):
                break

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
