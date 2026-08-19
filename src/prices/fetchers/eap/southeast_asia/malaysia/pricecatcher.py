"""KPDNHEP PriceCatcher (data.gov.my) — Malaysia's official daily price-
monitoring program across 500+ registered premises nationwide (wet markets,
supermarkets, minimarkets, hypermarkets), 758 SKUs (chicken, meat, seafood,
vegetables, fruit, rice, flour, noodles, oils/fats, eggs, dairy/milk powder,
nuts/pulses, spices, sauces, sugar, beverages, plus a minority of non-food
items ridden along on the same monitoring program).

Bulk static files, no auth, no rate limit:
- pricecatcher_{YYYY-MM}.csv  -- daily (date, premise_code, item_code, price)
- lookup_item.csv             -- item_code -> item, unit, item_group, item_category
- lookup_premise.csv          -- premise_code -> premise, address, premise_type,
                                  state, district

Whole-catalog walker: one monthly file per month since cutoff, no filtering.
COICOP is deferred to the downstream classifier/food-gate.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://storage.data.gov.my/pricecatcher"
_SOURCE_KEY = "my_pricecatcher"
_IDENT = ["source_key", "observation_date", "item_name", "notes"]


def _month_range(cutoff: date, today: date) -> list[tuple[int, int]]:
    months = []
    year, month = cutoff.year, cutoff.month
    while (year, month) <= (today.year, today.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _fetch_csv(session, url: str) -> pd.DataFrame | None:
    try:
        r = session.get(url, timeout=120)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] GET failed for %s: %s", _SOURCE_KEY, url, exc)
        return None
    return pd.read_csv(io.StringIO(r.text), low_memory=False)


def fetch_my_pricecatcher(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    items = _fetch_csv(session, f"{_BASE}/lookup_item.csv")
    premises = _fetch_csv(session, f"{_BASE}/lookup_premise.csv")
    if items is None or premises is None:
        return None
    items["item_code"] = pd.to_numeric(items["item_code"], errors="coerce")
    premises["premise_code"] = pd.to_numeric(premises["premise_code"], errors="coerce")

    today = datetime.now(timezone.utc).date()
    frames: list[pd.DataFrame] = []
    for year, month in _month_range(cutoff, today):
        url = f"{_BASE}/pricecatcher_{year}-{month:02d}.csv"
        df = _fetch_csv(session, url)
        if df is None or df.empty:
            logger.info("[%s] no data at %s", _SOURCE_KEY, url)
            continue
        df["observation_date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["item_code"] = pd.to_numeric(df["item_code"], errors="coerce")
        df["premise_code"] = pd.to_numeric(df["premise_code"], errors="coerce")
        df = df[
            df["observation_date"].notna()
            & (df["observation_date"] > cutoff)
            & df["price"].notna()
            & (df["price"] > 0)
        ]
        if df.empty:
            continue

        df = df.merge(items, on="item_code", how="left")
        df = df.merge(premises, on="premise_code", how="left")

        item_name = (
            df["item"].fillna("").astype(str).str.strip()
            + " ("
            + df["unit"].fillna("").astype(str).str.strip()
            + ")"
        ).str.strip()
        notes = (
            df["item_category"].fillna("").astype(str).str.strip()
            + "/"
            + df["item_group"].fillna("").astype(str).str.strip()
            + "; premise="
            + df["premise"].fillna("").astype(str).str.strip()
            + " ("
            + df["premise_type"].fillna("").astype(str).str.strip()
            + "), "
            + df["state"].fillna("").astype(str).str.strip()
        )

        ts = get_scrape_ts()
        out = pd.DataFrame(
            {
                "observation_date": df["observation_date"].astype(str),
                "period_kind": "daily",
                "country": "malaysia",
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": df["price"].round(2),
                "currency": "MYR",
                "unit": df["unit"].fillna("").astype(str).str.strip(),
                "source_url": url,
                "notes": notes,
                "scrape_ts": ts,
            }
        )
        out["observation_hash"] = out.apply(
            lambda row: make_hash(row.to_dict(), _IDENT), axis=1
        )
        frames.append(out)
        logger.info("[%s] %s -> %d rows", _SOURCE_KEY, url, len(out))

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)
