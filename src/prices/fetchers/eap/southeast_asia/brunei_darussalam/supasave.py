"""Supa Save Brunei branch storefronts via the WooCommerce Store API."""

from __future__ import annotations

import html
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, make_hash

_COUNTRY = "Brunei Darussalam"
_CURRENCY = "BND"
_IDENT = ["source_key", "observation_date", "item_name", "source_url"]
_PER_PAGE = 100
_MAX_PAGES = 100

_BROWSER_HEADERS = {
    # A full Chrome header set triggers the site's protection layer, while the
    # WooCommerce endpoint accepts simple JSON requests.
    "Accept": "application/json",
    "User-Agent": "python-requests/2.32",
}


def _price_from_woo(prices: dict) -> float | None:
    raw = prices.get("price")
    if raw is None:
        return None
    try:
        minor = int(prices.get("currency_minor_unit", 0) or 0)
        value = int(raw) / (10**minor) if minor else int(raw)
    except (TypeError, ValueError):
        return None
    return value


def _category_from_woo(product: dict) -> str | None:
    categories = product.get("categories") or []
    names = [
        html.unescape(c.get("name", "")).strip()
        for c in categories
        if isinstance(c, dict) and c.get("name")
    ]
    return " > ".join(names) or None


def _fetch_branch(
    cutoff: date,
    *,
    source_key: str,
    base_url: str,
    subnational_area: str,
) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    try:
        import requests
    except ImportError:  # pragma: no cover - requests is a repo dependency.
        return None

    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    rows: list[dict] = []

    for page in range(1, _MAX_PAGES + 1):
        resp = session.get(
            base_url,
            params={"per_page": _PER_PAGE, "page": page},
            timeout=45,
        )
        resp.raise_for_status()
        products = resp.json()
        if not isinstance(products, list) or not products:
            break

        scrape_ts = get_scrape_ts()
        for product in products:
            if not isinstance(product, dict):
                continue
            prices = product.get("prices") or {}
            price = _price_from_woo(prices)
            name = html.unescape(str(product.get("name") or "")).strip()
            if price is None or not name:
                continue

            row = {
                "observation_date": today.isoformat(),
                "period_kind": "current",
                "country": _COUNTRY,
                "subnational_area": subnational_area,
                "source_key": source_key,
                "coicop_code": None,
                "item_name": name[:500],
                "price_local": price,
                "currency": prices.get("currency_code") or _CURRENCY,
                "unit": None,
                "source_url": product.get("permalink") or base_url,
                "notes": _category_from_woo(product),
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

        if len(products) < _PER_PAGE:
            break

    if not rows:
        return None
    return pd.DataFrame(rows)


def fetch_bn_supasave_seria(cutoff: date) -> pd.DataFrame | None:
    return _fetch_branch(
        cutoff,
        source_key="bn_supasave_seria",
        base_url="https://seria.supasave.com.bn/wp-json/wc/store/v1/products",
        subnational_area="Seria",
    )


def fetch_bn_supasave_gadong(cutoff: date) -> pd.DataFrame | None:
    return _fetch_branch(
        cutoff,
        source_key="bn_supasave_gadong",
        base_url="https://gadong.supasave.com.bn/wp-json/wc/store/v1/products",
        subnational_area="Gadong",
    )
