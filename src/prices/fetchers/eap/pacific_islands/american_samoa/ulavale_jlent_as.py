"""Ulavale/J Len T American Samoa apparel, home decor, and gift prices."""

from __future__ import annotations

import html
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API = "https://www.ulavalesamoa.com/wp-json/wc/store/products"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_ulavale_jlent"
_IDENT = ["source_key", "observation_date", "item_name", "source_url"]
_PER_PAGE = 100
_MAX_PAGES = 10

_EXCLUDED_CATEGORIES = {
    "Corned Beef",
    "Food",
    "Palusami canned",
    "Pacific Corned Beef Pisupo",
    "UMU Bundle",
}
_EXCLUDED_NAME_WORDS = (
    "coconut cream",
    "corned beef",
    "palusami",
    "reverse withdrawal",
    "timtam",
)


def _price(prices: dict) -> float | None:
    raw = prices.get("price")
    if raw is None:
        return None
    try:
        minor = int(prices.get("currency_minor_unit", 0) or 0)
        value = int(raw) / (10**minor) if minor else int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _categories(product: dict) -> list[str]:
    return [
        html.unescape(str(cat.get("name") or "")).strip()
        for cat in product.get("categories") or []
        if isinstance(cat, dict) and cat.get("name")
    ]


def _keep(product: dict, item_name: str, cats: list[str]) -> bool:
    lowered_name = item_name.lower()
    if any(word in lowered_name for word in _EXCLUDED_NAME_WORDS):
        return False
    return not (set(cats) & _EXCLUDED_CATEGORIES)


def _row(product: dict, obs_date: date, ts: str) -> dict | None:
    prices = product.get("prices") or {}
    price = _price(prices)
    if price is None or not product.get("is_in_stock", True):
        return None
    item_name = html.unescape(str(product.get("name") or "")).strip()
    if not item_name:
        return None
    cats = _categories(product)
    if not _keep(product, item_name, cats):
        return None
    row = {
        "observation_date": obs_date.isoformat(),
        "period_kind": "current",
        "country": _COUNTRY,
        "subnational_area": "Pago Pago",
        "source_key": _SOURCE_KEY,
        "coicop_code": None,
        "item_name": item_name[:500],
        "price_local": round(price, 2),
        "currency": prices.get("currency_code") or _CURRENCY,
        "unit": "item",
        "source_url": product.get("permalink") or "https://www.ulavalesamoa.com/",
        "notes": f"categories={' > '.join(cats)}" if cats else "",
        "scrape_ts": ts,
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def fetch_as_ulavale_jlent(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = get_session()
    session.headers.update(
        {
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "Mozilla/5.0",
        }
    )

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set[str] = set()

    for page in range(1, _MAX_PAGES + 1):
        resp = session.get(
            _API, params={"per_page": _PER_PAGE, "page": page}, timeout=45
        )
        resp.raise_for_status()
        products = resp.json()
        if not isinstance(products, list) or not products:
            break
        for product in products:
            if not isinstance(product, dict):
                continue
            row = _row(product, today, ts)
            if not row or row["observation_hash"] in seen:
                continue
            seen.add(row["observation_hash"])
            rows.append(row)
        if len(products) < _PER_PAGE:
            break

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
