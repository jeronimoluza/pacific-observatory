"""
AguCheck — agucheck.com, a small crowdsourced Maldives grocery
price-comparison app ("Compare grocery and general goods prices across
the Maldives").

React SPA (Vite build), no server-rendered data. Playwright network
trace found a PocketBase backend at pb.agucheck.com exposing three
public REST collections, no auth:

  /api/collections/shops/records
  /api/collections/items/records
  /api/collections/prices/records?expand=item,shop&sort=-date

This is a genuinely tiny, crowdsourced dataset (5 shops, 48 items, 56
price records total as of 2026-09-11) -- OCR-submitted receipts per the
`added_by: "OCR Scan"` field on price rows. Small but real MVR prices
across multiple named Male'-area shops; wide/mixed categories (Dairy,
Bread & Bakery, etc.) -> coicop_classification: classifier.
"""

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://pb.agucheck.com/api/collections/prices/records"
_SITE_URL = "https://agucheck.com/"
_COUNTRY = "Maldives"
_CURRENCY = "MVR"
_SOURCE_KEY = "mv_agucheck"

_IDENT = ["source_key", "observation_date", "item_name", "subnational_area", "price_local"]


def fetch_mv_agucheck(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    rows = []
    page = 1
    while True:
        resp = session.get(
            _BASE,
            params={"page": page, "perPage": 200, "sort": "-date", "expand": "item,shop"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("items", [])
        if not items:
            break
        for rec in items:
            date_str = rec.get("date")
            if not date_str:
                continue
            try:
                obs_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            if obs_date <= cutoff:
                continue
            price = rec.get("price")
            if price is None or float(price) <= 0:
                continue
            expand = rec.get("expand") or {}
            item = expand.get("item") or {}
            shop = expand.get("shop") or {}
            item_name = item.get("item_name")
            if not item_name:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": float(price),
                "currency": _CURRENCY,
                "unit": rec.get("unit") or "each",
                "subnational_area": shop.get("location") or item.get("location"),
                "source_url": _SITE_URL,
                "notes": f"shop={shop.get('name') or item.get('shop_name')}",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
        if page >= int(payload.get("totalPages", 1) or 1):
            break
        page += 1

    if not rows:
        return None
    logger.info(f"mv_agucheck: {len(rows)} new price observations")
    return pd.DataFrame(rows)
