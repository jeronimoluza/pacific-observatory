"""Vinmonopolet (Norway) — state alcohol monopoly, full catalogue walk.

Norway's only legal off-premise alcohol retailer runs a public Hybris/SAP
Commerce OCC search API that needs no auth. Re-verified live 2026-08-06:
GET https://www.vinmonopolet.no/vmpws/v2/vmp/products/search?fields=FULL&query=:relevance
-> 200, JSON, `pagination.totalResults` 35602 across `pagination.totalPages`
1484 (the API silently clamps any requested pageSize to 24, so a full walk
is ~1,484 sequential requests). Sample row: 'Sierra Tequila Reposado' NOK
450.70, volume 70 cl. Prices are the single national administered price
(no per-store variation), so this is treated as an official_avg feed rather
than a retailer_sku one.

Each product carries a stable numeric `code`, so `code` (not `name`) anchors
the dedup identity — same convention as other whole-catalog walkers in this
repo. Only `status == "aktiv"` (currently for sale) rows are kept.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.vinmonopolet.no/vmpws/v2/vmp/products/search"
_COUNTRY = "Norway"
_CURRENCY = "NOK"
_SOURCE_KEY = "no_vinmonopolet"
_IDENT = ["source_key", "observation_date", "code"]
_MAX_PAGES = 1600  # guardrail above the ~1,484 seen live


def _iter_pages(session, max_pages: int = _MAX_PAGES):
    page = 0
    total_pages = None
    while total_pages is None or page < total_pages:
        if page >= max_pages:
            logger.warning("[%s] hit max_pages guardrail at page %d", _SOURCE_KEY, page)
            break
        resp = session.get(
            _SEARCH_URL,
            params={"fields": "FULL", "query": ":relevance", "currentPage": page},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        total_pages = data.get("pagination", {}).get("totalPages", page + 1)
        products = data.get("products", [])
        if not products:
            break
        yield products
        page += 1


def fetch_no_vinmonopolet(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        logger.info(
            "[%s] obs_date %s <= cutoff %s — already fetched today",
            _SOURCE_KEY,
            obs_date,
            cutoff,
        )
        return None

    session = get_session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    ts = get_scrape_ts()
    rows: list[dict] = []
    for products in _iter_pages(session):
        for p in products:
            if p.get("status") and p["status"] != "aktiv":
                continue
            name = (p.get("name") or "").strip()
            code = p.get("code")
            price = (p.get("price") or {}).get("value")
            if not name or not code or price is None:
                continue
            volume = (p.get("volume") or {}).get("value")
            category = (p.get("main_category") or {}).get("name", "")
            country_of_origin = (p.get("main_country") or {}).get("name", "")
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "daily",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "code": code,
                "item_name": name,
                "price_local": round(float(price), 2),
                "currency": _CURRENCY,
                "unit": f"{volume:g}cl" if volume else "bottle",
                "source_url": f"https://www.vinmonopolet.no{p.get('url', '')}",
                "notes": f"category={category}; origin={country_of_origin}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            del row["code"]
            rows.append(row)
    if not rows:
        logger.warning("[%s] no rows extracted", _SOURCE_KEY)
        return None
    logger.info("[%s] %d rows total (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
