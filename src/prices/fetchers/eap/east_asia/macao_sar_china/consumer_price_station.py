"""Macao Consumer Council (消費者委員會) "Price Station" (物價站) -- official
multi-supermarket item-level price comparison.

The public page (`consumer.gov.mo/commodity/price_station_type.aspx?type=t1`)
embeds a Next.js SPA at `api03.consumer.gov.mo/app/supermarket/` (a different
backend than the DSEC CPI service in `dsec_cpi.py`, confirmed via Playwright
network trace). The SPA's SSR HTML carries the payload inline as
`__NEXT_DATA__` JSON -- no auth, no key, plain GET.

`itemlist_price_range?lang=en&category=` (empty category) returns the full
top-level category list (14 categories: Rice, Cereal Product, Cooking Oil,
Canned Food, Seasoning, Beverage, Milk Product, Infant Product, Household
Cleansing Product, Personal care products, Snacks, Frozen/refrigerated
Foods, Paper Products, Spreads) under `pageProps.categories` -- discovered
dynamically each run rather than hardcoded, mirroring hk/online_price_watch.py.

`itemlist_price_range?lang=en&category=<id>` then returns `pageProps.rows`:
one entry per commodity item with `min_price`/`max_price` (the range observed
across surveyed Macao supermarkets) plus a bilingual/trilingual `item` object
(name_cn/name_zh/name_en/name_pt, quantity_cn/zh/en/pt). No per-item update
date is exposed in the payload (unlike HK's opw endpoint), so this fetcher
snapshots with the request date as observation_date -- same convention as
Talaad Thai (`th/talaadthai.py`) for a rolling-window endpoint without dates.
price_local is the midpoint of min_price/max_price (same convention as
Talaad Thai); the raw range is preserved in `notes` for auditability.

Catalog spans multiple COICOP divisions (Rice/Canned/Seasoning/Beverage/Milk/
Snacks -> 01; Household Cleansing -> 05; Personal care -> 12; Infant Product
mixes 01 formula and 12 diapers) -- not narrow to one class, so COICOP
tagging is deferred to the downstream classifier (same call as HK's
online_price_watch.py).

Emits PriceObservation rows.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://api03.consumer.gov.mo/app/supermarket/itemlist_price_range"
_LANDING_URL = (
    "https://www.consumer.gov.mo/commodity/price_station_type.aspx?lang=en&type=t1"
)
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_consumer_price_station"

_NEXT_DATA_RE = re.compile(
    r'__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

_IDENT = ["source_key", "observation_date", "item_name", "notes"]


def _get_page_props(session, params: dict) -> dict:
    resp = session.get(_BASE, params=params, timeout=30)
    resp.raise_for_status()
    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        raise ValueError("no __NEXT_DATA__ payload found")
    data = json.loads(m.group(1))
    return data["props"]["pageProps"]


def _discover_categories(session) -> list[dict]:
    props = _get_page_props(session, {"lang": "en", "category": ""})
    return props.get("categories") or []


def _walk_category(
    session, category_id: int, cutoff: date, obs_date: date
) -> list[dict]:
    props = _get_page_props(session, {"lang": "en", "category": category_id})
    rows_in = props.get("rows") or []
    ts = get_scrape_ts()
    rows: list[dict] = []

    if obs_date <= cutoff:
        return rows

    for entry in rows_in:
        item = entry.get("item") or {}
        item_name = (item.get("name_en") or item.get("name_zh") or "").strip()
        if not item_name:
            continue
        min_p, max_p = entry.get("min_price"), entry.get("max_price")
        if min_p is None or max_p is None:
            continue
        try:
            min_p, max_p = float(min_p), float(max_p)
        except (TypeError, ValueError):
            continue
        if not (0 < min_p <= max_p < 1_000_000):
            continue
        price = round((min_p + max_p) / 2, 2)
        unit = (
            item.get("quantity_en") or item.get("quantity_zh") or ""
        ).strip() or None
        code = item.get("code", "")

        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _LANDING_URL,
            "notes": f"min_price={min_p}; max_price={max_p}; code={code}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return rows


def fetch_mo_consumer_price_station(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update({"Referer": _LANDING_URL})

    try:
        categories = _discover_categories(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] category discovery failed: %s", _SOURCE_KEY, exc)
        return None
    if not categories:
        logger.warning("[%s] no categories discovered", _SOURCE_KEY)
        return None

    obs_date = datetime.now(timezone.utc).date()

    rows: list[dict] = []
    for cat in categories:
        cat_id = cat.get("_id")
        if cat_id is None:
            continue
        try:
            rows.extend(_walk_category(session, cat_id, cutoff, obs_date))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] category %s failed: %s", _SOURCE_KEY, cat_id, exc)
            continue

    logger.info(
        "[%s] %d categories walked, %d rows (cutoff=%s)",
        _SOURCE_KEY,
        len(categories),
        len(rows),
        cutoff,
    )
    return pd.DataFrame(rows) if rows else None
