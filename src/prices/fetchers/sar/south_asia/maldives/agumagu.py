"""
AguMagu — Maldives Ministry of Economic Development national commodity
price-monitoring platform (agumagu.trade.gov.mv).

Not server-rendered (Next.js App Router SPA, no price data in the
initial HTML). Playwright network trace found a single JSON endpoint,
`/api/bootstrap`, that returns the WHOLE dataset in one call (~7MB, no
pagination, no auth): 118 monitored items (staples, produce, fish,
household consumables), 510 outlets across all 21 Maldivian atolls, and
~29k individual (item, outlet, day) price observations with a rolling
~30-day recency window (`cheapest_window_days`).

Wide, mixed basket (rice/vegetables/fish alongside diapers/baby
shampoo) — `coicop_classification: classifier`, no `_COICOP_MAP`.

Each `prices` entry is one observed price at one outlet on one day —
treated as `period_kind="snapshot"`, not an average. `availability`
"OUT_OF_STOCK" rows carry `price: 0.0` and are dropped (not a real
price observation).
"""

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = "https://agumagu.trade.gov.mv/api/bootstrap"
_SITE_URL = "https://agumagu.trade.gov.mv/"
_COUNTRY = "Maldives"
_CURRENCY = "MVR"
_SOURCE_KEY = "mv_agumagu"

_IDENT = ["source_key", "observation_date", "item_name", "subnational_area", "city", "price_local"]


def fetch_mv_agumagu(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_API_URL, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    items = {it["id"]: it for it in payload.get("items", [])}
    outlets = {o["id"]: o for o in payload.get("outlets", [])}

    rows = []
    for p in payload.get("prices", []):
        if p.get("availability") == "OUT_OF_STOCK":
            continue
        price = p.get("price")
        if price is None or float(price) <= 0:
            continue
        recorded_at = p.get("recorded_at")
        if not recorded_at:
            continue
        try:
            obs_date = datetime.fromisoformat(recorded_at).date()
        except ValueError:
            continue
        if obs_date <= cutoff:
            continue

        item = items.get(p.get("item_id"))
        if not item:
            continue
        item_name = item.get("name")
        if not item_name:
            continue
        unit = ((item.get("unit") or {}).get("abbreviation")) or "each"

        outlet = outlets.get(p.get("outlet_id")) or {}
        loc = outlet.get("location") or {}
        atoll_name = (loc.get("atoll") or {}).get("name")
        island_name = loc.get("island")

        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": float(price),
            "currency": _CURRENCY,
            "unit": unit,
            "subnational_area": atoll_name,
            "city": island_name,
            "source_url": _SITE_URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None
    logger.info(f"mv_agumagu: {len(rows)} new price observations")
    return pd.DataFrame(rows)
