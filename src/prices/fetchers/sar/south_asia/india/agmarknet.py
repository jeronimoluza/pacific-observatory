"""AGMARKNET — India daily wholesale mandi (market) prices, via data.gov.in.

agmarknet.gov.in itself 403s from outside India (confirmed via curl and a real
Chromium instance — a network-level geofence, not a bot check) and its e-NAM
mirror at enam.gov.in/dashboard/agmarknet returns HTTP 500 on every dynamic
endpoint (Agm_ctrl/*, Ajax_ctrl/*, Liveprice_ctrl/*), reproduced with a real
Playwright browser session, so the backend is down site-wide rather than
bot-gated. The same dataset is republished on the Open Government Data (OGD)
platform (data.gov.in) as "Variety-wise Daily Market Prices Data of Commodity"
and is reachable: the resource's public preview page
(https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity)
embeds a working sample `api-key` for its own resource id, which this fetcher
uses against the documented api.data.gov.in REST endpoint.

Re-verified live 2026-08-07: resource id 35985678-0d79-46b4-9ed6-6f13308a1d24,
81M+ total records, `updated_date` on the resource metadata is same-day.
Sorting/filtering by Arrival_Date confirms rows for the current day are
already posted (e.g. 4 rows for 07/08/2026 at time of probe, 17,471 rows for
06/08/2026 — a full day's catalog). Sample: Commodity 'Ginger(Green)',
Variety 'Green Ginger', Market 'Siliguri APMC', District Darjeeling, State
West Bengal, Modal_Price 11500 (Min 11000 / Max 12000). Modal_Price is
Rs./Quintal — data.gov.in's own field description for this resource states
"Modal Price (Rs./Quintal)" and this holds across every commodity in the
dataset, not just a sampled subset.

This is a whole-catalog walker, not a targeted extractor: every commodity /
variety / market / state the API returns is emitted, unfiltered. The API
supports an exact-match `filters[Arrival_Date]=DD/MM/YYYY` (India date
order) that returns a full day's national catalog in one call when `limit`
is set above the day's row count (a single day has run comfortably to
~17.5K rows with `limit=20000`, no server-side cap observed at that size);
a defensive offset loop still guards against a day that exceeds `_LIMIT`.
Walks backward from today, stopping at `cutoff` or after `_MAX_DAYS_BACK`
days, mirroring the bounded-backward-walk pattern used by the Nepal
Kalimati market fetcher — a full historical backfill of this dataset is
several orders of magnitude larger than one onboarding run should pull.

COICOP is deferred to the downstream classifier — item_name is the WFP-style
free-text commodity (+ variety when the variety differs from the commodity
name), and the catalog spans essentially the entire food division 01 plus
several non-food agricultural commodities (cotton, jute, spices used
industrially, flowers).
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_RESOURCE_ID = "35985678-0d79-46b4-9ed6-6f13308a1d24"
_API_KEY = "579b464db66ec23bdd000001cdc3b564546246a772a26393094f5645"
_API_URL = f"https://api.data.gov.in/resource/{_RESOURCE_ID}"
_RESOURCE_PAGE = (
    "https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity"
)
_COUNTRY = "India"
_CURRENCY = "INR"
_UNIT = "quintal (100 kg)"
_SOURCE_KEY = "in_agmarknet"
_IDENT = ["source_key", "observation_date", "item_name", "market", "grade"]
_MAX_DAYS_BACK = 7
_LIMIT = 20000
_EMPTY_VARIETY = {"", "other", "-", "na", "n/a"}


def _num(val) -> float | None:
    try:
        f = float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _fetch_day(session, day: date) -> list[dict]:
    date_str = day.strftime("%d/%m/%Y")
    records: list[dict] = []
    offset = 0
    while True:
        try:
            resp = session.get(
                _API_URL,
                params={
                    "api-key": _API_KEY,
                    "format": "json",
                    "limit": _LIMIT,
                    "offset": offset,
                    "filters[Arrival_Date]": date_str,
                },
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for %s: %s", _SOURCE_KEY, date_str, exc)
            break
        batch = payload.get("records") or []
        records.extend(batch)
        total = int(payload.get("total") or 0)
        offset += len(batch)
        if not batch or offset >= total:
            break
        time.sleep(2)
    return records


def _rows_for_day(session, day: date) -> list[dict]:
    ts = get_scrape_ts()
    out: list[dict] = []
    for rec in _fetch_day(session, day):
        commodity = str(rec.get("Commodity") or "").strip()
        if not commodity:
            continue
        price = _num(rec.get("Modal_Price"))
        if price is None:
            continue
        variety = str(rec.get("Variety") or "").strip()
        same_as_commodity = variety.lower() == commodity.lower()
        item_name = (
            commodity
            if variety.lower() in _EMPTY_VARIETY or same_as_commodity
            else f"{commodity} ({variety})"
        )
        market = str(rec.get("Market") or "").strip()
        grade = str(rec.get("Grade") or "").strip()
        state = str(rec.get("State") or "").strip()
        district = str(rec.get("District") or "").strip()
        min_p = _num(rec.get("Min_Price"))
        max_p = _num(rec.get("Max_Price"))
        # NOTE: PriceObservation's optional geographic columns (subnational_area,
        # city, district) are documented in fetcher_pattern.md but writers.py's
        # PRICE_COLUMNS does not include them -- any fetcher that sets them has
        # those values silently dropped on write. State/district/market survive
        # here only via `notes`.
        row = {
            "observation_date": day.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "market": market,
            "grade": grade,
            "source_url": _RESOURCE_PAGE,
            "notes": (
                f"state={state or 'n/a'}; district={district or 'n/a'}; "
                f"market={market or 'n/a'}; grade={grade or 'n/a'}; "
                f"min={min_p}; max={max_p} Rs./Quintal"
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("market")
        row.pop("grade")
        out.append(row)
    return out


def fetch_in_agmarknet(cutoff: date) -> pd.DataFrame | None:
    # The shared data.gov.in sample api-key throttles under burst load (429s
    # observed after a handful of rapid calls, clearing after ~20-40s); a
    # generous retry/backoff plus a deliberate pause between days keeps this
    # fetcher under that ceiling instead of tripping it every run.
    session = get_session(retries=8, backoff=3.0)
    today = date.today()
    all_rows: list[dict] = []
    for i in range(_MAX_DAYS_BACK):
        day = today - timedelta(days=i)
        if day <= cutoff:
            break
        day_rows = _rows_for_day(session, day)
        logger.info("[%s] %s -> %d rows", _SOURCE_KEY, day, len(day_rows))
        all_rows.extend(day_rows)
        time.sleep(2)
    logger.info("[%s] %d total rows (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
