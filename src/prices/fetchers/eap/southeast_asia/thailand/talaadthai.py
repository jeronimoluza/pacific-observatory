"""Talaad Thai wholesale market — daily reference prices, full fresh-produce catalog.

Talaad Thai (ตลาดไท) is Thailand's largest wholesale produce market, publishing
daily min/max reference prices for ~2,000 fresh commodities (fruit, vegetables,
herbs, tubers, meat, fish & seafood). Each product has a public page at
/en/products/<id> whose embedded Next.js __NEXT_DATA__ carries the current and
previous daily price snapshot.

Enumeration: the catalog backend (mgt-backend.talaadthai.com) is WAF-blocked
from outside Thailand and robots.txt disallows the sibling *.json data endpoint,
so this fetcher walks numeric product ids over the robots-allowed HTML pages and
parses __NEXT_DATA__. Ids are sparse/clustered (~1–2500 and ~4500–5500 live,
2500–4500 largely empty); dead ids return fast and are skipped.

COICOP is deferred to the downstream classifier — the catalog spans too many
leaves (and rotates) to hand-map; item names are the products' English titles.
Snapshot tracker: emits the current + previous daily snapshot and accumulates
history as it runs.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://talaadthai.com"
_COUNTRY = "Thailand"
_CURRENCY = "THB"
_SOURCE_KEY = "th_talaadthai"

_MAX_ID = 5600  # newest product ids observed ~5300; buffer for catalog growth
_WORKERS = 6

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
_NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_IDENT = ["source_key", "observation_date", "item_name"]


def _product(session, pid: int) -> dict | None:
    try:
        resp = session.get(f"{_BASE}/en/products/{pid}", timeout=20)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data.get("props", {}).get("pageProps", {}).get("product")


def _rows_for(product: dict | None, pid: int, cutoff: date) -> list[dict]:
    if not product:
        return []
    title = product.get("title") or {}
    name = (title.get("en") or title.get("th") or "").strip()
    if not name:
        return []
    unit_raw = product.get("unit") or ""
    unit = (
        "kg"
        if "กิโลกรัม" in unit_raw or unit_raw.lower() in ("kg", "kilogram")
        else (unit_raw or "kg")
    )
    snaps = (product.get("pricingData") or {}).get(
        "latestPriceDiffProductSnapShot", {}
    ).get("data") or {}
    url = f"{_BASE}/en/products/{pid}"
    out = []
    for key in ("current", "prev"):
        snap = snaps.get(key)
        if not snap:
            continue
        raw, lo, hi = snap.get("date"), snap.get("minPrice"), snap.get("maxPrice")
        if not raw or lo is None or hi is None:
            continue
        obs_date = raw[:10]
        if date.fromisoformat(obs_date) <= cutoff:
            continue
        price = round((float(lo) + float(hi)) / 2, 2)
        if not 0 < price < 1_000_000:
            continue
        row = {
            "observation_date": obs_date,
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": unit,
            "subnational_area": None,
            "source_url": url,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
            "notes": f"wholesale min={lo} max={hi} THB/{unit}",
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def _fetch(cutoff: date, ids) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update({"User-Agent": _BROWSER_UA})

    def work(pid: int) -> list[dict]:
        return _rows_for(_product(session, pid), pid, cutoff)

    rows: list[dict] = []
    seen: set = set()
    with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        for res in ex.map(work, ids):
            for r in res:
                key = (r["item_name"], r["observation_date"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(r)
    logger.info("[%s] %d rows from %d ids", _SOURCE_KEY, len(rows), len(ids))
    return pd.DataFrame(rows) if rows else None


def fetch_th_talaadthai(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, range(1, _MAX_ID + 1))
