"""Xinfadi (新发地) wholesale market — Beijing's largest F&B wholesale market.

China's first genuine F&B price-level fetcher: the previous only working
grocery source (suning spider, channel:supermarket) is a retail catalog,
while every other China source is pharmacy or a crowd-sourced cost-of-living
aggregator. Xinfadi publishes a same-day catalogue of wholesale min/max/avg
prices across four families — vegetables (蔬菜), fruit (水果), meat/poultry/
eggs (肉禽蛋), and aquatic products (水产) — via an open, unauthenticated JSON
endpoint (`getPriceData.html`) with server-side date filtering
(`pubDateStartTime`/`pubDateEndTime`) and pagination (`current`/`limit`).
~450-550 items/day; verified live 2026-08-11 (e.g. 大白菜/Chinese cabbage
0.7-0.8 CNY/斤 from Hebei; 白条猪/dressed pork loin 7.0 CNY/斤).

`unitInfo` is overwhelmingly 斤 (jin, 0.5kg) with a handful of 个/只/筐/箱
(each/head/basket/crate) exceptions; 斤 prices are converted to CNY/kg
(×2), everything else is passed through with its native unit label so no
per-unit price gets silently mis-scaled.

Bounded like the Nepal Kalimati fetcher: walks a fixed lookback window from
today rather than from `cutoff`, so a stale or very old cutoff does not
trigger a multi-year backfill against a source with 759k+ historical rows.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "http://www.xinfadi.com.cn/getPriceData.html"
_COUNTRY = "China"
_CURRENCY = "CNY"
_SOURCE_KEY = "cn_xinfadi_wholesale"
_IDENT = ["source_key", "observation_date", "item_name", "place", "spec_info", "unit"]
_MAX_DAYS_BACK = 30
_LIMIT = 1000
_MAX_PAGES = 50  # safety cap: 50k rows/run ceiling regardless of window size

_JIN_TO_KG = 2.0


def _unit_price(unit_raw: str, avg_price: float) -> tuple[str, float]:
    u = (unit_raw or "").strip()
    if u == "斤":
        return "kg", round(avg_price * _JIN_TO_KG, 2)
    if u == "公斤":
        return "kg", avg_price
    return (u or "unit"), avg_price


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if 0 < f < 1_000_000 else None


def _fetch_page(session, start: date, end: date, current: int) -> dict | None:
    try:
        resp = session.post(
            _URL,
            data={
                "limit": _LIMIT,
                "current": current,
                "pubDateStartTime": start.isoformat(),
                "pubDateEndTime": end.isoformat(),
                "prodPcatid": "",
                "prodCatid": "",
                "prodName": "",
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page %d fetch failed: %s", _SOURCE_KEY, current, exc)
        return None


def collect_window(
    session, ts: str, start: date, end: date, cutoff: date, pause: float = 0.0
) -> list[dict]:
    """Page through [start, end] and return parsed rows newer than ``cutoff``."""
    rows: list[dict] = []
    seen: set = set()
    current = 1
    total_count = None
    while current <= _MAX_PAGES:
        payload = _fetch_page(session, start, end, current)
        if not payload:
            break
        batch = payload.get("list") or []
        if total_count is None:
            total_count = payload.get("count")
        if not batch:
            break
        for r in batch:
            pub_date_raw = str(r.get("pubDate", "")).strip()
            try:
                obs_date = pd.to_datetime(pub_date_raw).date()
            except (ValueError, TypeError):
                continue
            if obs_date <= cutoff:
                continue
            avg_price = _num(r.get("avgPrice"))
            if avg_price is None:
                continue
            name = str(r.get("prodName", "")).strip()
            if not name:
                continue
            unit, price = _unit_price(str(r.get("unitInfo", "")), avg_price)
            place = str(r.get("place", "")).strip()
            spec = str(r.get("specInfo", "")).strip()
            cat = str(r.get("prodCat", "")).strip()
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "daily",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": name,
                "price_local": price,
                "currency": _CURRENCY,
                "unit": unit,
                "place": place,
                "spec_info": spec,
                "source_url": _URL,
                "notes": (
                    f"wholesale {cat}; low={r.get('lowPrice')} high={r.get('highPrice')} "
                    f"origin={place or 'n/a'}; spec={spec or 'n/a'}"
                ),
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            key = row["observation_hash"]
            if key in seen:
                continue
            seen.add(key)
            del row["place"]
            del row["spec_info"]
            rows.append(row)
        if len(batch) < _LIMIT:
            break
        if total_count is not None and current * _LIMIT >= total_count:
            break
        current += 1
        if pause:
            time.sleep(pause)

    return rows


def fetch_cn_xinfadi_wholesale(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    start = max(today - timedelta(days=_MAX_DAYS_BACK - 1), cutoff + timedelta(days=1))
    if start > today:
        logger.info("[%s] cutoff already covers today; nothing to fetch", _SOURCE_KEY)
        return None

    rows = collect_window(get_session(), get_scrape_ts(), start, today, cutoff)
    logger.info(
        "[%s] %d rows (window=%s..%s, cutoff=%s)",
        _SOURCE_KEY,
        len(rows),
        start,
        today,
        cutoff,
    )
    return pd.DataFrame(rows) if rows else None
