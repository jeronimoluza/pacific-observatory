"""Hong Kong Consumer Council "Online Price Watch" — official daily multi-supermarket
item-level price comparison across 9 chains (Wellcome, PARKnSHOP, Market Place, Watsons,
Mannings, AEON, DCH Food Mart, Sasa, Lung Fung). The catalog spans 10 top-level divisions
(~360 leaf categories: Bakery/Cereals/Spreads, Dairy/Soy/Eggs, Candies/Biscuits/Snacks,
Rice/Oil/Canned/Produce/Meat, Noodles/Cooking needs, Drinks, Milk powder/Baby care,
Personal care, Household/Pet, Beer/Wines/Spirits) — not narrow to one COICOP class, so
COICOP tagging is deferred to the downstream classifier.

The site (`online-price-watch.consumer.org.hk`) server-renders category pages but loads
product/price data via a JSON endpoint (`POST /opw/getPriceList/<cat1>/<cat2>/<cat3>`) —
no auth, no CSRF token required. The full category tree isn't exposed as its own API call,
so it's discovered by parsing the site's own nav menu (identical markup on every
`/opw/list/...` page) rather than hardcoding all leaf codes — a category added or removed
by the Consumer Council is picked up automatically on the next run.

Each leaf item's JSON carries per-supermarket sub-entries under `data`; this fetcher emits
one PriceObservation row per (item, supermarket) pair, storing the supermarket code in
`notes` since PriceObservation has no dedicated retailer column.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://online-price-watch.consumer.org.hk/opw"
_TREE_URL = f"{_BASE}/list/018/010/030"
_API_URL = f"{_BASE}/getPriceList"
_COUNTRY = "Hong Kong"
_CURRENCY = "HKD"
_SOURCE_KEY = "hk_online_price_watch"
_PAGE_LENGTH = 100
# The endpoint tarpits (silent read-timeout, not a 429) after a sustained burst of
# sequential POSTs with no pacing — confirmed transient: a leaf that times out
# recovers within seconds once requests slow down. Pace every leaf and retry once.
_LEAF_DELAY_S = 0.3
_RETRY_DELAY_S = 3.0

_LEAF_RE = re.compile(r'<a href="/opw/list/(\d{3}/\d{3}/\d{3})" class="link">')
_IDENT = ["source_key", "observation_date", "item_name", "notes"]


def _discover_leaves(session) -> list[str]:
    """Parse the site's own nav menu for the full leaf-category tree."""
    resp = session.get(_TREE_URL, timeout=30)
    resp.raise_for_status()
    return sorted(set(_LEAF_RE.findall(resp.text)))


def _walk_leaf(session, leaf: str, cutoff: date) -> list[dict]:
    cat1, cat2, cat3 = leaf.split("/")
    rows: list[dict] = []
    start = 0
    ts = get_scrape_ts()
    while True:
        resp = session.post(
            f"{_API_URL}/{cat1}/{cat2}/{cat3}",
            params={
                "start": start,
                "length": _PAGE_LENGTH,
                "order": "asc",
                "sortby": "index",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(
                "[%s] leaf %s HTTP %s — stopping leaf",
                _SOURCE_KEY,
                leaf,
                resp.status_code,
            )
            break
        payload = resp.json()
        items = payload.get("data") or []
        if not items:
            break

        for item in items:
            item_name = (item.get("nameEN") or item.get("name") or "").strip()
            if not item_name:
                continue
            code = item.get("code", "")
            for sm_code, entry in (item.get("data") or {}).items():
                price_raw = entry.get("Price")
                if price_raw in (None, "", "-"):
                    continue
                try:
                    price = float(price_raw)
                except (TypeError, ValueError):
                    continue
                if not 0 < price < 1_000_000:
                    continue
                obs_date_str = entry.get("PriceDateShort") or item.get("lastUpdate")
                if not obs_date_str:
                    continue
                try:
                    obs_date = date.fromisoformat(obs_date_str)
                except ValueError:
                    continue
                if obs_date <= cutoff:
                    continue

                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "snapshot",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": item_name,
                    "price_local": round(price, 2),
                    "currency": _CURRENCY,
                    "unit": "each",
                    "source_url": f"{_BASE}/list/{leaf}",
                    "notes": f"supermarket={sm_code}; code={code}; leaf={leaf}",
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

        if not payload.get("more", False) or len(items) < _PAGE_LENGTH:
            break
        start += _PAGE_LENGTH

    return rows


def fetch_hk_online_price_watch(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update({"X-Requested-With": "XMLHttpRequest", "Referer": _TREE_URL})

    try:
        leaves = _discover_leaves(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] category-tree discovery failed: %s", _SOURCE_KEY, exc)
        return None
    if not leaves:
        logger.warning(
            "[%s] no leaf categories discovered — check nav markup", _SOURCE_KEY
        )
        return None

    rows: list[dict] = []
    for leaf in leaves:
        for attempt in (1, 2):
            try:
                rows.extend(_walk_leaf(session, leaf, cutoff))
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 1:
                    logger.warning(
                        "[%s] leaf %s failed (attempt 1): %s — retrying",
                        _SOURCE_KEY,
                        leaf,
                        exc,
                    )
                    time.sleep(_RETRY_DELAY_S)
                    continue
                logger.warning(
                    "[%s] leaf %s failed after retry: %s", _SOURCE_KEY, leaf, exc
                )
        time.sleep(_LEAF_DELAY_S)

    logger.info(
        "[%s] %d leaves walked, %d rows (cutoff=%s)",
        _SOURCE_KEY,
        len(leaves),
        len(rows),
        cutoff,
    )
    return pd.DataFrame(rows) if rows else None
