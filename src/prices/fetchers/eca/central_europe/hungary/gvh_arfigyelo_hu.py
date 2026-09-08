"""Hungary GVH Arfigyelo (statutory price monitor) -- https://arfigyelo.gvh.hu/.

NOT a scrape of shops -- this is the Hungarian Competition Authority's
(GVH) own statutory database, run under Act L of 2025, Chapter V.
Retailers are legally obliged to upload the next day's prices by end of
the preceding day. It is ground truth other Hungarian retailer scrapes
should be validated against, not itself a full-assortment catalogue --
coverage is the mandated basket (5,000+ products / 140 categories /
1,817 stores across 6 national chains + 3 drugstore chains).

The front end is a Vue/Vite SPA; a Playwright network trace (2026-09-06)
found a completely open JSON backend requiring no auth:

  - `GET /api/categories` -> nested tree (9 top-level divisions, 42
    "level 2" categories, deeper leaf nodes below those).
  - `GET /api/products-by-category/<level2_id>` -> already returns the
    FULL flattened product list for that whole subtree (confirmed: id
    2010 "Sajt" returns leaf-level items like "S-Budget tejszinu
    omlesztett sajt 100 g" directly, without a further per-leaf call) --
    this is also exactly the granularity the real page's own network
    calls use (observed calls: 2001, 2010, 2014, 2015, 2046), so this
    fetcher walks the 42 level-2 ids rather than every leaf.

Each product carries `pricesOfChainStores[]`, one entry per chain
(observed: Spar and others), each with a `prices[]` array of
`{type, amount, unitAmount}` -- `type` is one of NORMAL / PRIOR / LOYALTY
per the GVH's three-price-field design (napi ar / korabbi ar / torzsvasarloi
ar). Every price row is emitted with the chain name and price type
recorded in `notes` since the PriceObservation schema has no dedicated
retailer-chain column.

Verified live: category 2010 -> "S-Budget pulykasonkas omlesztett sajt
100 g" -> Spar, NORMAL, HUF 135.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CATEGORIES_URL = "https://arfigyelo.gvh.hu/api/categories"
_PRODUCTS_URL = "https://arfigyelo.gvh.hu/api/products-by-category/{cat_id}"
_COUNTRY = "Hungary"
_CURRENCY = "HUF"
_SOURCE_KEY = "hu_gvh_arfigyelo"
_IDENT = ["source_key", "observation_date", "item_name", "notes"]


def _level2_category_ids(tree: dict) -> list[int]:
    ids = []
    for top in tree.get("categories") or []:
        for node in top.get("categoryNodes") or []:
            cid = node.get("id")
            if cid is not None:
                ids.append(cid)
    return ids


def _rows_for_category(payload: dict, obs_date: date, ts: str) -> list[dict]:
    out: list[dict] = []
    for product in payload.get("products") or []:
        name = (product.get("name") or "").strip()
        if not name:
            continue
        for chain in product.get("pricesOfChainStores") or []:
            chain_name = chain.get("name") or "unknown"
            for price in chain.get("prices") or []:
                amount = price.get("amount")
                if amount in (None, "", 0):
                    continue
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "daily",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": name,
                    "price_local": round(float(amount), 2),
                    "currency": _CURRENCY,
                    "unit": product.get("unit"),
                    "source_url": "https://arfigyelo.gvh.hu/",
                    "notes": f"chain={chain_name};price_type={price.get('type')}",
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                out.append(row)
    return out


def fetch_hu_gvh_arfigyelo(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    obs_date = date.today()
    if obs_date <= cutoff:
        logger.info("[%s] cutoff %s not yet passed", _SOURCE_KEY, cutoff)
        return None

    try:
        resp = session.get(_CATEGORIES_URL, timeout=30)
        resp.raise_for_status()
        tree = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] category fetch failed: %s", _SOURCE_KEY, exc)
        return None

    cat_ids = _level2_category_ids(tree)
    logger.info("[%s] %d level-2 categories", _SOURCE_KEY, len(cat_ids))

    ts = get_scrape_ts()
    rows: list[dict] = []
    for cat_id in cat_ids:
        try:
            resp = session.get(_PRODUCTS_URL.format(cat_id=cat_id), timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] category %s fetch failed: %s", _SOURCE_KEY, cat_id, exc)
            continue
        rows.extend(_rows_for_category(payload, obs_date, ts))

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
