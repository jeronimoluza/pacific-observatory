"""Refresh the fuel dashboard FX cache with missing currencies and dates.

Reads the existing cache at data/cpi/fuel_prices/global/forex/fx_cache.csv,
identifies gaps (missing currencies, stale dates), fetches only what's needed
from the exchangerate.host API, and saves the updated cache.

Usage:
    export EXCHANGERATEHOST_API_KEY=...
    python scripts/refresh_fx_cache.py
"""

from __future__ import annotations

import datetime
import os
import sys
import time

import pandas as pd
import requests

# All currencies used in the fuel enriched data
REQUIRED_CURRENCIES = sorted(
    {
        "AUD",
        "CNY",
        "FJD",
        "HKD",
        "IDR",
        "JPY",
        "KHR",
        "KRW",
        "LAK",
        "MMK",
        "MNT",
        "MYR",
        "NZD",
        "PGK",
        "PHP",
        "SBD",
        "SGD",
        "THB",
        "TOP",
        "TWD",
        "VND",
        "VUV",
        "WST",
    }
)

CACHE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "cpi",
    "fuel_prices",
    "global",
    "forex",
    "fx_cache.csv",
)

API_URL = "https://api.exchangerate.host/timeframe"
MAX_BATCH_DAYS = 364  # API limit


MAX_RETRIES = 4
RETRY_DELAYS = [10, 30, 60, 120]  # seconds


def _fetch_batch(
    api_key: str,
    start: datetime.date,
    end: datetime.date,
    currencies: list[str],
) -> dict[str, dict[str, float]]:
    """Fetch FX rates for one batch (max 365 days), with retry on 429."""
    params = {
        "access_key": api_key,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "source": "USD",
        "currencies": ",".join(currencies),
    }
    for attempt in range(MAX_RETRIES + 1):
        resp = requests.get(API_URL, params=params, timeout=30)
        if resp.status_code == 429:
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAYS[attempt]
                print(
                    f"    Rate limited — waiting {wait}s (attempt {attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
        resp.raise_for_status()
        break
    data = resp.json()
    if not data.get("success") or "quotes" not in data:
        err = data.get("error", {})
        raise RuntimeError(f"API error for {start}→{end}: {err}")
    return {
        date_str: {k.replace("USD", "", 1): v for k, v in day_rates.items()}
        for date_str, day_rates in data["quotes"].items()
    }


def main() -> None:
    api_key = os.environ.get("EXCHANGERATEHOST_API_KEY")
    if not api_key:
        print("ERROR: set EXCHANGERATEHOST_API_KEY env var first.")
        sys.exit(1)

    cache_path = os.path.normpath(CACHE_PATH)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    # Load existing cache
    if os.path.exists(cache_path):
        cache = pd.read_csv(cache_path)
        cache["date"] = cache["date"].astype(str).str[:10]
        print(f"Loaded {len(cache):,} cached rows from {cache_path}")
    else:
        cache = pd.DataFrame(columns=["date", "currency_iso", "rate_usd_to_local"])
        print("No existing cache — starting fresh.")

    cached_currencies = set(cache["currency_iso"].unique()) if len(cache) else set()
    cached_dates = set(cache["date"].unique()) if len(cache) else set()

    # Determine what we need
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    # For currencies already in cache, extend from their max date
    # For new currencies, fetch from a reasonable start (2020-01-01)
    new_currencies = sorted(set(REQUIRED_CURRENCIES) - cached_currencies)
    existing_currencies = sorted(set(REQUIRED_CURRENCIES) & cached_currencies)

    fetch_jobs: list[tuple[str, str, list[str]]] = []  # (start, end, currencies)

    if new_currencies:
        start = "2020-01-01"
        print(f"New currencies ({len(new_currencies)}): {new_currencies}")
        print(f"  Will fetch {start} → {yesterday}")
        fetch_jobs.append((start, yesterday.isoformat(), new_currencies))

    if existing_currencies and cached_dates:
        max_cached = max(cached_dates)
        next_day = datetime.date.fromisoformat(max_cached) + datetime.timedelta(days=1)
        if next_day <= yesterday:
            print(
                f"Extending {len(existing_currencies)} existing currencies: {next_day} → {yesterday}"
            )
            fetch_jobs.append(
                (next_day.isoformat(), yesterday.isoformat(), existing_currencies)
            )
        else:
            print("Existing currencies are up to date.")

    if not fetch_jobs:
        print("Nothing to fetch.")
        return

    # Fetch in batches
    new_rows: list[dict] = []
    for start_str, end_str, currencies in fetch_jobs:
        batch_start = datetime.date.fromisoformat(start_str)
        final_end = datetime.date.fromisoformat(end_str)
        total_days = (final_end - batch_start).days
        total_batches = (total_days // MAX_BATCH_DAYS) + 1
        batch_num = 0

        while batch_start <= final_end:
            batch_end = min(
                batch_start + datetime.timedelta(days=MAX_BATCH_DAYS), final_end
            )
            batch_num += 1
            print(
                f"  Batch {batch_num}/{total_batches}: "
                f"{batch_start} → {batch_end} ({len(currencies)} currencies)"
            )
            rates = _fetch_batch(api_key, batch_start, batch_end, currencies)
            for date_str, day_rates in rates.items():
                for currency, rate in day_rates.items():
                    if currency in set(REQUIRED_CURRENCIES):
                        new_rows.append(
                            {
                                "date": date_str,
                                "currency_iso": currency,
                                "rate_usd_to_local": rate,
                            }
                        )
            batch_start = batch_end + datetime.timedelta(days=1)
            if batch_start <= final_end:
                time.sleep(3)

    print(f"Fetched {len(new_rows):,} new rate rows.")

    # Merge with cache
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        cache = pd.concat([cache, new_df], ignore_index=True)
        cache = cache.drop_duplicates(subset=["date", "currency_iso"], keep="last")

    # Forward-fill weekends/holidays per currency
    all_dates = pd.date_range(
        start=cache["date"].min(), end=yesterday, freq="D"
    ).strftime("%Y-%m-%d")

    filled = []
    for currency in sorted(cache["currency_iso"].unique()):
        cur_df = cache[cache["currency_iso"] == currency][["date", "rate_usd_to_local"]]
        full = pd.DataFrame({"date": all_dates, "currency_iso": currency})
        full = full.merge(cur_df, on="date", how="left")
        full["rate_usd_to_local"] = full["rate_usd_to_local"].ffill()
        filled.append(full.dropna(subset=["rate_usd_to_local"]))

    cache = pd.concat(filled, ignore_index=True)
    cache = cache.sort_values(["currency_iso", "date"]).reset_index(drop=True)
    cache.to_csv(cache_path, index=False)
    print(
        f"Saved {len(cache):,} rows ({len(cache['currency_iso'].unique())} currencies) to {cache_path}"
    )


if __name__ == "__main__":
    main()
