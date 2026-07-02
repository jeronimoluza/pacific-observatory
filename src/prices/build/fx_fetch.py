"""Prices-local FX cache pre-warm helper.

Uses the shared fetcher (cpi.analysis.core.forex.fetch_fx_rates) to pull
current currency rates and upsert them into the prices FX cache, additively:
pre-existing (currency, date) rows that are not re-fetched are preserved.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

import pandas as pd

from cpi.analysis.core import forex
from prices.build.fx import PRICES_FX_CACHE

logger = logging.getLogger(__name__)

_FX_COLUMNS = ["currency", "date", "rate_usd_to_local"]

PRICES_CURRENCIES = ["FJD", "AUD", "NPR", "PHP", "HKD", "KHR", "TWD"]


def prewarm_fx_cache(
    currencies: list[str] | None = None,
    cache_path: Path | None = None,
    start: str | None = None,
    end: str | None = None,
) -> int:
    """Fetch rates for ``currencies`` and upsert them into the prices FX cache.

    When ``start``/``end`` are omitted the latest available date (yesterday,
    UTC) is used as a single-day range, since the shared fetcher only supports
    date ranges. Returns the number of fetched (added/updated) rows.
    """
    currencies = list(PRICES_CURRENCIES if currencies is None else currencies)
    cache_path = Path(PRICES_FX_CACHE if cache_path is None else cache_path)

    if start is None or end is None:
        latest = datetime.date.today() - datetime.timedelta(days=1)
        start = start or latest.isoformat()
        end = end or latest.isoformat()

    raw = forex.fetch_fx_rates(start, end, currencies)

    rows: list[dict[str, object]] = []
    for date_str, day_rates in raw.items():
        obs_date = pd.Timestamp(date_str).normalize()
        for currency, rate in day_rates.items():
            rows.append(
                {
                    "currency": str(currency).upper(),
                    "date": obs_date,
                    "rate_usd_to_local": rate,
                }
            )
    fetched = pd.DataFrame(rows, columns=_FX_COLUMNS)

    existing = pd.DataFrame(columns=_FX_COLUMNS)
    if cache_path.exists():
        try:
            existing = pd.read_csv(cache_path, low_memory=False)
        except pd.errors.EmptyDataError:
            existing = pd.DataFrame(columns=_FX_COLUMNS)
        for col in _FX_COLUMNS:
            if col not in existing.columns:
                existing[col] = None
        existing["date"] = pd.to_datetime(
            existing["date"], errors="coerce"
        ).dt.normalize()
        existing = existing[_FX_COLUMNS]

    # Fetched rows go last so keep="last" lets fresh values win on collisions
    # while non-refetched (currency, date) rows are preserved.
    combined = pd.concat([existing, fetched], ignore_index=True)
    combined = combined.dropna(subset=["currency", "date"])
    combined = combined.drop_duplicates(subset=["currency", "date"], keep="last")
    combined = combined.sort_values(["currency", "date"]).reset_index(drop=True)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(cache_path, index=False)

    logger.info("Pre-warmed %s FX rows into %s", len(fetched), cache_path)
    return int(len(fetched))
