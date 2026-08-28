"""Taiwan MOA agricultural wholesale prices — full daily catalogue across markets.

The Ministry of Agriculture open-data platform (data.moa.gov.tw) publishes daily
transaction prices for four commodity families through separate endpoints, each
with its own schema:

  produce  FarmTransData  UnitId=037 — 900+ fruit/veg crops (and cut flowers) by market
  hog      AnimalTransData UnitId=026 — live hogs by market (NT$/kg liveweight)
  sheep    SheepTransData  UnitId=276 — goats & sheep by product & market
  poultry  PoultryTransBoiledChickenData UnitId=056 — broiler chicken + eggs (national)

The hog/sheep/poultry endpoints cover the COICOP live-animal leaves (01.1.2.1.x)
that retail never carries; the produce endpoint covers the fresh fruit/veg
sourcing gaps. This fetcher is general on purpose — it pulls every commodity
from every endpoint, not just the missing leaves, and lets the downstream
division-01 classifier gate non-food rows (e.g. the cut flowers in the produce
feed).

Each endpoint returns its most-recent window newest-first (capped ~5.5k–10k
rows), so incremental daily runs accumulate history; a first run only sees the
last few days for the high-cardinality produce feed. Prices are NT$/kg; the
per-market origin is kept in `notes` and folded into the dedup hash so the
`item_name` stays a clean product string for the embedder. COICOP is deferred.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://data.moa.gov.tw/Service/OpenData/FromM"
_COUNTRY = "Taiwan"
_CURRENCY = "TWD"
_SOURCE_KEY = "tw_moa_wholesale"
_UNIT = "kg"
_IDENT = ["source_key", "observation_date", "item_name", "market"]
_CLOSED = {"休市", "", None}


def _roc_compact(s: str) -> date | None:
    # "1150804" -> 2026-08-04
    s = (s or "").strip()
    if len(s) < 7 or not s.isdigit():
        return None
    try:
        return date(int(s[:-4]) + 1911, int(s[-4:-2]), int(s[-2:]))
    except ValueError:
        return None


def _roc_dotted(s: str) -> date | None:
    # "115.08.05" -> 2026-08-05
    parts = (s or "").strip().split(".")
    if len(parts) != 3:
        return None
    try:
        return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _iso(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def _slash(s: str) -> date | None:
    try:
        return datetime.strptime((s or "").strip(), "%Y/%m/%d").date()
    except ValueError:
        return None


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if 0 < f < 1_000_000 else None


def _parse_produce(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        crop = (r.get("作物名稱") or "").strip()
        if crop in _CLOSED:
            continue
        d = _roc_dotted(r.get("交易日期"))
        price = _num(r.get("平均價"))
        if d is None or price is None or d <= cutoff:
            continue
        out.append(
            {
                "obs_date": d,
                "market": (r.get("市場名稱") or "").strip(),
                "item_name": crop,
                "price": price,
                "note": (
                    f"produce; high={r.get('上價')} mid={r.get('中價')} low={r.get('下價')} "
                    f"vol={r.get('交易量')}"
                ),
            }
        )
    return out


def _parse_hog(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        d = _roc_compact(r.get("交易日期"))
        price = _num(r.get("成交頭數-平均價格"))
        if d is None or price is None or d <= cutoff:
            continue
        out.append(
            {
                "obs_date": d,
                "market": (r.get("市場名稱") or "").strip(),
                "item_name": "毛豬 (live hog)",
                "price": price,
                "note": (
                    f"live hog auction; avg_weight={r.get('成交頭數-平均重量')} "
                    f"head={r.get('成交頭數-總數')}"
                ),
            }
        )
    return out


def _parse_sheep(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        name = (r.get("productName") or "").strip()
        d = _iso(r.get("transDate"))
        price = _num(r.get("avgPrice"))
        if not name or d is None or price is None or d <= cutoff:
            continue
        out.append(
            {
                "obs_date": d,
                "market": (r.get("name") or r.get("shortName") or "").strip(),
                "item_name": name,
                "price": price,
                "note": (
                    f"sheep/goat auction; avg_weight={r.get('avgWeight')} "
                    f"qty={r.get('quantity')} high={r.get('highestPrice')}"
                ),
            }
        )
    return out


_POULTRY_SKIP = {"日期", "農曆"}


def _parse_poultry(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        d = _slash(r.get("日期"))
        if d is None or d <= cutoff:
            continue
        for col, val in r.items():
            if col in _POULTRY_SKIP:
                continue
            price = _num(val)
            if price is None:
                continue
            out.append(
                {
                    "obs_date": d,
                    "market": "",
                    "item_name": col.strip(),
                    "price": price,
                    "note": "poultry/egg national quote",
                }
            )
    return out


_ENDPOINTS = [
    ("FarmTransData", "037", _parse_produce),
    ("AnimalTransData", "026", _parse_hog),
    ("SheepTransData", "276", _parse_sheep),
    ("PoultryTransBoiledChickenData", "056", _parse_poultry),
]


def _load(session, path: str, unit_id: str) -> list | None:
    url = f"{_BASE}/{path}.aspx?UnitId={unit_id}&IsTransData=1"
    try:
        resp = session.get(url, timeout=200)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s] %s (UnitId=%s) fetch failed: %s", _SOURCE_KEY, path, unit_id, exc
        )
        return None
    try:
        return json.loads(resp.content.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "[%s] %s (UnitId=%s) parse failed: %s", _SOURCE_KEY, path, unit_id, exc
        )
        return None


def fetch_tw_moa_wholesale(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )
    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set = set()
    for path, unit_id, parser in _ENDPOINTS:
        records = _load(session, path, unit_id)
        if not records:
            continue
        parsed = parser(records, cutoff)
        for p in parsed:
            row = {
                "observation_date": p["obs_date"].isoformat(),
                "period_kind": "daily",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": p["item_name"],
                "price_local": round(p["price"], 2),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": f"{_BASE}/{path}.aspx?UnitId={unit_id}",
                "notes": f"wholesale {p['note']}; market={p['market']}",
                "scrape_ts": ts,
                "market": p["market"],
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            key = row["observation_hash"]
            if key in seen:
                continue
            seen.add(key)
            del row["market"]
            rows.append(row)
        logger.info(
            "[%s] %s (UnitId=%s): %d rows", _SOURCE_KEY, path, unit_id, len(parsed)
        )
    logger.info("[%s] %d rows total (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
