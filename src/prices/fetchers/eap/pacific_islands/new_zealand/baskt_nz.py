"""Baskt (baskt.nz) — third-party NZ grocery price comparison database.

Baskt scrapes latest observed prices across seven NZ grocery chains (Woolworths/
Countdown, New World, PAK'nSAVE, Farro, Fresh Choice, SuperValue, The Warehouse)
and publishes them via a public, unauthenticated REST API documented at
https://www.baskt.nz/developers. NZ's own major chains are individually
Akamai/Foodstuffs-blocked (see references/known_blockers.md, Akamai section);
Baskt is the only realistic route to cross-store price dispersion for NZ
grocery at this granularity.

One ``GET /api/v1/items?q=<term>&chain=<slug>`` call returns both item metadata
and a ``latestPrices`` array of per-location observations, so a single request
per (search term, chain) is enough — the per-item
``/api/v1/items/comparison`` endpoint gives a fuller panel but costs one request
per item, which the rate limit makes unaffordable.

**Rate limit: 45 requests/minute** (``x-ratelimit-limit: 45``, 429 carries
``retry-after``). Requests are paced below that ceiling and 429s are honoured
rather than retried blindly; the ~16-term curated list (not a full-catalog walk)
keeps the run proportionate to a daily snapshot and respects the site's explicit
"not a bulk export feed" notice on /developers.

``latestPrices`` is per (item, location); rows are collapsed to one national
average per (item, chain) — mirroring how the WFP fetcher collapses per-market
rows — with the store count and price range kept in ``notes``.
"""

from __future__ import annotations

import logging
import time
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://www.baskt.nz/api/v1"
_COUNTRY = "New Zealand"
_CURRENCY = "NZD"
_SOURCE_KEY = "nz_baskt"

# Server allows 45 req/min; pace well under it and honour retry-after on 429.
_REQUEST_INTERVAL_S = 1.6
_MAX_RETRY_AFTER_S = 75
_ITEMS_LIMIT = 25

_IDENT = ["source_key", "observation_date", "chain", "item_id", "unit"]

_CHAIN_LABELS: dict[str, str] = {
    "countdown": "Woolworths",
    "new-world": "New World",
    "paknsave": "PAK'nSAVE",
    "farro": "Farro",
    "freshchoice": "Fresh Choice",
    "supervalue": "SuperValue",
    "the-warehouse": "The Warehouse",
}

_SEARCH_TERMS = [
    "milk",
    "cheese",
    "butter",
    "eggs",
    "bread",
    "chicken",
    "beef mince",
    "bacon",
    "banana",
    "apple",
    "potato",
    "tomato",
    "rice",
    "pasta",
    "sugar",
    "coffee",
]


def _get_items(session, term: str, chain: str) -> dict | None:
    """One paced GET; returns the response payload's ``data`` block."""
    params = {"q": term, "chain": chain, "limit": _ITEMS_LIMIT}
    for _ in range(2):
        try:
            resp = session.get(f"{_BASE}/items", params=params, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] items failed (q=%s, chain=%s): %s", _SOURCE_KEY, term, chain, exc
            )
            return None
        if resp.status_code == 429:
            wait = min(
                int(resp.headers.get("retry-after", 30) or 30), _MAX_RETRY_AFTER_S
            )
            logger.info("[%s] rate-limited, sleeping %ss", _SOURCE_KEY, wait)
            time.sleep(wait)
            continue
        if not resp.ok:
            logger.warning(
                "[%s] items HTTP %s (q=%s, chain=%s)",
                _SOURCE_KEY,
                resp.status_code,
                term,
                chain,
            )
            return None
        try:
            return resp.json().get("data", {})
        except ValueError as exc:
            logger.warning(
                "[%s] items non-JSON (q=%s, chain=%s): %s",
                _SOURCE_KEY,
                term,
                chain,
                exc,
            )
            return None
    return None


def _build_row(
    item: dict, price_rows: list[dict], chain: str, cutoff: date
) -> dict | None:
    valid = [
        p for p in price_rows if p.get("priceCents") is not None and p.get("observedAt")
    ]
    if not valid:
        return None

    obs_dates = pd.to_datetime(
        [p["observedAt"] for p in valid], errors="coerce", utc=True
    )
    obs_date = obs_dates.max()
    if pd.isna(obs_date):
        return None
    obs_date = obs_date.date()
    if obs_date <= cutoff:
        return None

    cents = [p["priceCents"] for p in valid]
    mean_price = (sum(cents) / len(cents)) / 100
    if not 0 < mean_price < 1e6:
        return None
    lo, hi = min(cents) / 100, max(cents) / 100

    name = str(item.get("name") or "").strip()
    if not name:
        return None
    pack = str(item.get("packSize") or "").strip()
    item_name = (
        f"{name} ({pack})" if pack and pack.lower() not in name.lower() else name
    )

    row = {
        "observation_date": obs_date.isoformat(),
        "period_kind": "snapshot",
        "country": _COUNTRY,
        "source_key": _SOURCE_KEY,
        "item_name": item_name,
        "price_local": round(mean_price, 2),
        "currency": _CURRENCY,
        "unit": "each",
        "source_url": f"https://www.baskt.nz/items/{item.get('id')}",
        "notes": (
            f"chain={_CHAIN_LABELS.get(chain, chain)}; n_locations={len(valid)}; "
            f"range=${lo:.2f}-${hi:.2f}; gtin={item.get('gtin') or 'na'}"
        ),
        "scrape_ts": get_scrape_ts(),
        "chain": chain,
        "item_id": item.get("id"),
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    row.pop("chain")
    row.pop("item_id")
    return row


def fetch_nz_baskt(cutoff: date) -> pd.DataFrame | None:
    session = get_session(retries=0)
    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []

    for term in _SEARCH_TERMS:
        for chain in _CHAIN_LABELS:
            data = _get_items(session, term, chain)
            time.sleep(_REQUEST_INTERVAL_S)
            if not data:
                continue

            by_item: dict[str, list[dict]] = {}
            for p in data.get("latestPrices", []):
                by_item.setdefault(str(p.get("itemId")), []).append(p)

            for item in data.get("items", []):
                item_id = str(item.get("id") or "")
                key = (chain, item_id)
                if not item_id or key in seen:
                    continue
                price_rows = by_item.get(item_id)
                if not price_rows:
                    continue
                seen.add(key)
                row = _build_row(item, price_rows, chain, cutoff)
                if row:
                    rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
