"""Currency conversion and FX rate utilities for cross-country comparisons."""

import os
import time
import datetime
import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

# Country slug -> capital timezone (IANA)
COUNTRY_TIMEZONES = {
    "australia": "Australia/Sydney",
    "cambodia": "Asia/Phnom_Penh",
    "fiji": "Pacific/Fiji",
    "indonesia": "Asia/Jakarta",
    "japan": "Asia/Tokyo",
    "south_korea": "Asia/Seoul",
    "papua_new_guinea": "Pacific/Port_Moresby",
    "philippines": "Asia/Manila",
    "samoa": "Pacific/Apia",
    "tonga": "Pacific/Tongatapu",
    "vanuatu": "Pacific/Efate",
    "vietnam": "Asia/Ho_Chi_Minh",
}

# Data currency code (from labels.json) -> ISO 4217
CURRENCY_TO_ISO = {
    "AUD": "AUD",
    "FJ": "FJD",
    "IDR": "IDR",
    "JPY": "JPY",
    "K": "PGK",
    "KHR": "KHR",
    "KRW": "KRW",
    "NZD": "NZD",
    "PHP": "PHP",
    "T": "TOP",
    "USD": "USD",
    "VND": "VND",
    "VNT": "VUV",
}


def normalize_currency(currency_code: str) -> str:
    """
    Map data currency codes to ISO 4217.

    Parameters
    ----------
    currency_code : str
        Currency code as it appears in the data (e.g., "FJ", "VNT", "K")

    Returns
    -------
    str
        ISO 4217 currency code (e.g., "FJD", "VUV", "PGK")

    Raises
    ------
    KeyError
        If the currency code is not recognized
    """
    code = currency_code.strip()
    if code in CURRENCY_TO_ISO:
        return CURRENCY_TO_ISO[code]
    raise KeyError(
        f"Unknown currency code: '{code}'. "
        f"Known codes: {sorted(CURRENCY_TO_ISO.keys())}"
    )


def convert_timezone(
    df: pd.DataFrame,
    date_col: str = "date",
    country_col: str = "country",
    source_tz: str = "America/Argentina/Buenos_Aires",
) -> pd.DataFrame:
    """
    Convert dates from source timezone to each country's local timezone.

    The scraping server is in Buenos Aires, so observation timestamps are in
    that timezone. This matters for FX rate lookups: Buenos Aires 23:00 on
    Jan 15 = Fiji 14:00 on Jan 16 -> different FX rate date.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with date and country columns
    date_col : str
        Name of the date column (default: "date")
    country_col : str
        Name of the country column (default: "country")
    source_tz : str
        Source timezone (default: "America/Argentina/Buenos_Aires")

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'date_local' (datetime) and 'date_local_date' (date) columns
    """
    df = df.copy()

    # Ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col])

    # Localize to source timezone (Buenos Aires)
    date_series = df[date_col]
    if date_series.dt.tz is None:
        date_series = date_series.dt.tz_localize(source_tz)
    else:
        date_series = date_series.dt.tz_convert(source_tz)

    # Convert to each country's local timezone.
    # We work in UTC and apply per-country offsets, then extract the local date.
    # Start with the source-tz series converted to UTC for a uniform base.
    utc_series = date_series.dt.tz_convert("UTC")
    df["date_local"] = utc_series  # default: UTC

    for country, tz in COUNTRY_TIMEZONES.items():
        mask = df[country_col] == country
        if mask.any():
            converted = date_series[mask].dt.tz_convert(tz)
            # Store as UTC-equivalent but remember local date
            df.loc[mask, "date_local"] = converted.dt.tz_convert("UTC")
            # Extract the *local* date (which may differ from UTC date)
            df.loc[mask, "date_local_date"] = converted.apply(
                lambda x: x.date() if pd.notna(x) else pd.NaT
            )

    # Handle countries not in COUNTRY_TIMEZONES (keep source tz date)
    missing_mask = (
        df["date_local_date"].isna()
        if "date_local_date" in df.columns
        else pd.Series(True, index=df.index)
    )
    if missing_mask.any():
        df.loc[missing_mask, "date_local_date"] = date_series[missing_mask].apply(
            lambda x: x.date() if pd.notna(x) else pd.NaT
        )

    # Ensure date_local_date is proper datetime for reliable min/max/merge
    df["date_local_date"] = pd.to_datetime(df["date_local_date"])

    return df


def fetch_fx_rates(
    start_date: str,
    end_date: str,
    currencies: List[str],
    api_key: Optional[str] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Fetch FX rates from exchangerate.host API using the timeframe endpoint.

    Splits the date range into 364-day batches (API limit is 365 days).
    Raises RuntimeError if any batch fails.

    Parameters
    ----------
    start_date : str
        Start date (YYYY-MM-DD)
    end_date : str
        End date (YYYY-MM-DD)
    currencies : list of str
        ISO 4217 currency codes (e.g., ["FJD", "PHP", "AUD"])
    api_key : str, optional
        API key. If None, reads from EXCHANGERATEHOST_API_KEY env var.

    Returns
    -------
    dict
        {date_str: {currency_iso: rate_usd_to_local}}
    """
    if api_key is None:
        api_key = os.environ.get("EXCHANGERATEHOST_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "EXCHANGERATEHOST_API_KEY environment variable is required for FX rate fetching. "
                "Set it or pass api_key parameter. Use --skip-ppp to skip PPP analysis."
            )

    currencies_str = ",".join(sorted(set(currencies)))

    return _fetch_timeframe(api_key, start_date, end_date, currencies_str)


def _fetch_timeframe(
    api_key: str, start_date: str, end_date: str, currencies_str: str
) -> Dict[str, Dict[str, float]]:
    """Fetch rates using the timeframe endpoint in 364-day batches."""
    url = "https://api.exchangerate.host/timeframe"
    max_days = 364

    batch_start = datetime.date.fromisoformat(start_date)
    final_end = datetime.date.fromisoformat(end_date)
    all_rates: Dict[str, Dict[str, float]] = {}

    batch_num = 0
    total_batches = ((final_end - batch_start).days // max_days) + 1

    while batch_start <= final_end:
        batch_end = min(batch_start + datetime.timedelta(days=max_days), final_end)
        batch_num += 1
        print(
            f"    Timeframe batch {batch_num}/{total_batches}: {batch_start} to {batch_end}"
        )

        params = {
            "access_key": api_key,
            "start_date": batch_start.isoformat(),
            "end_date": batch_end.isoformat(),
            "source": "USD",
            "currencies": currencies_str,
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success") or "quotes" not in data:
            error_info = data.get("error", {})
            raise RuntimeError(
                f"FX API batch {batch_num} failed ({batch_start} to {batch_end}): {error_info}"
            )

        for date_str, day_rates in data["quotes"].items():
            all_rates[date_str] = {
                k.replace("USD", "", 1): v for k, v in day_rates.items()
            }

        batch_start = batch_end + datetime.timedelta(days=1)

        # Sleep between batches to respect API rate limits
        if batch_start <= final_end:
            time.sleep(1)

    return all_rates


def build_fx_rate_table(
    df: pd.DataFrame,
    cache_path: str = "data/cpi/analysis/fx_cache.csv",
) -> pd.DataFrame:
    """
    Build a complete FX rate table, using a disk cache to avoid re-fetching.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'date_local_date' and 'currency' columns.
        Must have been processed by convert_timezone() first.
    cache_path : str
        Path to the FX rate cache CSV file

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: currency_iso, date, rate_usd_to_local
    """
    # Determine date range and currencies needed
    # date_local_date is a datetime64 column (may contain NaT)
    valid_dates = df["date_local_date"].dropna()
    start_date = valid_dates.min().date()  # pd.Timestamp -> datetime.date
    end_date = datetime.date.today() - datetime.timedelta(days=1)

    # Get unique ISO currencies (excluding USD which doesn't need conversion)
    unique_currencies = set()
    for code in df["currency"].dropna().unique():
        try:
            iso = normalize_currency(code)
            if iso != "USD":
                unique_currencies.add(iso)
        except KeyError:
            pass
    unique_currencies = sorted(unique_currencies)

    if not unique_currencies:
        return pd.DataFrame(columns=["currency_iso", "date", "rate_usd_to_local"])

    # Load existing cache — use string dates internally for reliable comparison
    cache = pd.DataFrame(columns=["currency_iso", "date", "rate_usd_to_local"])
    if os.path.exists(cache_path):
        cache = pd.read_csv(cache_path)
        cache["date"] = pd.to_datetime(cache["date"]).dt.strftime("%Y-%m-%d")
        print(f"    Loaded {len(cache):,} cached FX rates from {cache_path}")

    # Build full set of date strings we need
    all_dates = set()
    current = start_date
    while current <= end_date:
        all_dates.add(current.isoformat())
        current += datetime.timedelta(days=1)

    cached_dates = set()
    if len(cache) > 0:
        cached_dates = set(cache["date"].unique())

    missing_dates = all_dates - cached_dates

    if not missing_dates:
        print("    All FX rates found in cache, no API calls needed.")
        # Ensure date column is string for consistent merge later
        return cache

    # Fetch missing rates
    sorted_missing = sorted(missing_dates)
    fetch_start = sorted_missing[0]
    fetch_end = sorted_missing[-1]
    print(
        f"    Fetching FX rates for {len(missing_dates)} missing dates ({fetch_start} to {fetch_end})..."
    )

    raw_rates = fetch_fx_rates(fetch_start, fetch_end, unique_currencies)

    # Convert to DataFrame
    rows = []
    for date_str, day_rates in raw_rates.items():
        for currency, rate in day_rates.items():
            rows.append(
                {
                    "currency_iso": currency,
                    "date": date_str,
                    "rate_usd_to_local": rate,
                }
            )
    new_rates = pd.DataFrame(rows)

    # Merge with cache
    if len(new_rates) > 0:
        if len(cache) == 0:
            cache = new_rates
        else:
            cache = pd.concat([cache, new_rates], ignore_index=True)
        cache = cache.drop_duplicates(subset=["currency_iso", "date"], keep="last")

    # Forward-fill weekends/holidays: for each currency, fill gaps
    date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    date_strs = date_range.strftime("%Y-%m-%d")

    filled_rows = []
    for currency in unique_currencies:
        curr_rates = cache[cache["currency_iso"] == currency].copy()

        full_df = pd.DataFrame({"date": date_strs})
        full_df["currency_iso"] = currency

        if len(curr_rates) > 0:
            full_df = full_df.merge(
                curr_rates[["date", "rate_usd_to_local"]],
                on="date",
                how="left",
            )
        else:
            full_df["rate_usd_to_local"] = np.nan

        # Forward-fill missing rates (weekends/holidays)
        full_df["rate_usd_to_local"] = full_df["rate_usd_to_local"].ffill()
        filled_rows.append(full_df)

    if filled_rows:
        cache = pd.concat(filled_rows, ignore_index=True)

    # Save updated cache
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cache.to_csv(cache_path, index=False)
    print(f"    Saved {len(cache):,} FX rates to {cache_path}")

    return cache


def convert_to_usd(
    df: pd.DataFrame,
    fx_rates: pd.DataFrame,
    value_col: str = "unit_value",
) -> pd.DataFrame:
    """
    Convert prices to USD using FX rates.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with currency, date_local_date, and value_col columns
    fx_rates : pd.DataFrame
        FX rate table from build_fx_rate_table()
        Columns: currency_iso, date, rate_usd_to_local
    value_col : str
        Name of the price column to convert (default: "unit_value")

    Returns
    -------
    pd.DataFrame
        DataFrame with added columns:
        - currency_iso: ISO 4217 currency code
        - rate_usd_to_local: FX rate used
        - unit_value_usd: Price converted to USD
    """
    df = df.copy()

    # Add ISO currency codes
    df["currency_iso"] = df["currency"].apply(
        lambda x: normalize_currency(x) if pd.notna(x) else np.nan
    )

    # Merge FX rates — align date key types (df has datetime64, fx_rates has str)
    fx_merge = fx_rates.copy()
    fx_merge = fx_merge.rename(columns={"date": "date_local_date"})
    # Convert df date to string to match FX table format
    df["_merge_date"] = df["date_local_date"].dt.strftime("%Y-%m-%d")
    fx_merge = fx_merge.rename(columns={"date_local_date": "_merge_date"})
    df = df.merge(
        fx_merge[["currency_iso", "_merge_date", "rate_usd_to_local"]],
        on=["currency_iso", "_merge_date"],
        how="left",
    )
    df = df.drop(columns=["_merge_date"])

    # Convert to USD
    # USD rows: no conversion needed
    usd_mask = df["currency_iso"] == "USD"
    df.loc[usd_mask, "unit_value_usd"] = df.loc[usd_mask, value_col]
    df.loc[usd_mask, "rate_usd_to_local"] = 1.0

    # Other currencies: divide by rate
    non_usd_mask = ~usd_mask & df["rate_usd_to_local"].notna()
    df.loc[non_usd_mask, "unit_value_usd"] = (
        df.loc[non_usd_mask, value_col] / df.loc[non_usd_mask, "rate_usd_to_local"]
    )

    return df
