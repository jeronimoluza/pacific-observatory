"""supermarket.mn retail product cards.

The site is a Next.js supermarket storefront. Its homepage is server rendered
with product-card names, product links, and tugrik prices, which makes a small
retail-food snapshot available without browser automation.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_START_URL = "https://supermarket.mn/"
_COUNTRY = "Mongolia"
_SUBNATIONAL_AREA = "Ulaanbaatar"
_CURRENCY = "MNT"
_SOURCE_KEY = "mn_supermarket_mn"
_IDENT = ["source_key", "observation_date", "item_name", "source_url"]
_PRICE_RE = re.compile(r"([0-9][0-9,\s.]*)\s*₮")


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _parse_price(text: str) -> float | None:
    match = _PRICE_RE.search(text)
    if not match:
        return None
    raw = match.group(1).replace(",", "").replace(" ", "")
    try:
        price = float(raw)
    except ValueError:
        return None
    return price if price > 0 else None


def _nearest_card(anchor) -> object | None:
    for node in [anchor, *list(anchor.parents)[:8]]:
        text = node.get_text(" ", strip=True)
        if "₮" in text and len(text) < 700:
            return node
    return None


def _product_name(card, anchor) -> str:
    image = card.find("img") if hasattr(card, "find") else None
    if image and image.get("alt"):
        name = _clean_text(image.get("alt"))
        if name and name.lower() != "image":
            return name

    label = _clean_text(anchor.get_text(" ", strip=True))
    if label:
        return label

    text = card.get_text(" ", strip=True)
    parts = [
        part.strip()
        for part in re.split(r"Сагсанд хийх|Сагслах|[-]?\d+\s*%|" + _PRICE_RE.pattern, text)
        if part and part.strip() and part.strip() != "0"
    ]
    return _clean_text(parts[-1] if parts else "")


def _extract_products(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    today = date.today().isoformat()
    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    seen_urls: set[str] = set()

    for anchor in soup.select('a[href^="/product/"]'):
        href = anchor.get("href")
        if not href:
            continue
        product_url = urljoin(source_url, href)
        if product_url in seen_urls:
            continue
        card = _nearest_card(anchor)
        if card is None:
            continue
        card_text = card.get_text(" ", strip=True)
        price = _parse_price(card_text)
        if price is None:
            continue
        item_name = _product_name(card, anchor)
        if not item_name:
            continue
        parsed_url = urlparse(product_url)
        product_id = parsed_url.path.rsplit("/", 1)[-1]
        row = {
            "observation_date": today,
            "period_kind": "daily",
            "country": _COUNTRY,
            "subnational_area": _SUBNATIONAL_AREA,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "item",
            "source_url": product_url,
            "notes": f"homepage product card; product_id={product_id}",
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
        seen_urls.add(product_url)

    return rows


def fetch_mn_supermarket_mn(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] latest date %s <= cutoff %s", _SOURCE_KEY, today, cutoff)
        return None

    session = get_session()
    resp = session.get(_START_URL, timeout=45)
    resp.raise_for_status()
    rows = _extract_products(resp.text, _START_URL)
    logger.info("[%s] parsed %d homepage product rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
