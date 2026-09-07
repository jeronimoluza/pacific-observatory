"""Nomin hypermarket homepage product cards."""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_START_URL = "https://nomin.mn/"
_COUNTRY = "Mongolia"
_SUBNATIONAL_AREA = "Mongolia online"
_CURRENCY = "MNT"
_SOURCE_KEY = "mn_nomin"
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
    for node in [anchor, *list(anchor.parents)[:10]]:
        text = node.get_text(" ", strip=True)
        if "₮" in text and len(text) < 900:
            return node
    return None


def _product_name(card, anchor) -> str:
    image = card.find("img") if hasattr(card, "find") else None
    if image and image.get("alt"):
        alt = _clean_text(image.get("alt"))
        if alt and alt.lower() not in {"image", "product"}:
            return alt

    text = card.get_text(" ", strip=True)
    cleaned = _PRICE_RE.sub(" ", text)
    cleaned = re.sub(r"[-]?\s*\d+\s*%", " ", cleaned)
    cleaned = re.sub(r"\b0\b|Сагсанд хийх|Сагслах", " ", cleaned)
    return _clean_text(cleaned or anchor.get_text(" ", strip=True))


def fetch_mn_nomin(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        logger.info("[%s] latest date %s <= cutoff %s", _SOURCE_KEY, obs_date, cutoff)
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_START_URL, timeout=45)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen_urls: set[str] = set()
    for anchor in soup.select('a[href^="/p/"]'):
        href = anchor.get("href")
        if not href:
            continue
        product_url = urljoin(_START_URL, href)
        if product_url in seen_urls:
            continue
        card = _nearest_card(anchor)
        if card is None:
            continue
        price = _parse_price(card.get_text(" ", strip=True))
        if price is None:
            continue
        item_name = _product_name(card, anchor)
        if not item_name:
            continue
        product_id = urlparse(product_url).path.rsplit("/", 1)[-1]
        row = {
            "observation_date": obs_date.isoformat(),
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
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
        seen_urls.add(product_url)

    logger.info("[%s] parsed %d homepage product rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
