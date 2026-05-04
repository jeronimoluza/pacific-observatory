"""FX helpers for the migrated fuel build stage."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from cpi.analysis.core.forex import fetch_fx_rates

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FX_CACHE = _PROJECT_ROOT / "data" / "fuel" / "fx_cache.csv"
_FX_COLUMNS = ["currency", "date", "rate_usd_to_local"]


def _load_cache(cache_path: Path) -> pd.DataFrame:
    if not cache_path.exists():
        return pd.DataFrame(columns=_FX_COLUMNS)
    try:
        cache = pd.read_csv(cache_path, low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=_FX_COLUMNS)
    for col in _FX_COLUMNS:
        if col not in cache.columns:
            cache[col] = None
    cache["date"] = pd.to_datetime(cache["date"], errors="coerce").dt.normalize()
    cache["rate_usd_to_local"] = pd.to_numeric(
        cache["rate_usd_to_local"], errors="coerce"
    )
    return cache.dropna(subset=["currency", "date"]).copy()


def _fetch_missing_rates(
    currencies: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    if not currencies:
        return pd.DataFrame(columns=_FX_COLUMNS)
    try:
        raw = fetch_fx_rates(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            currencies,
        )
    except Exception as exc:
        logger.warning(
            "FX fetch unavailable; USD comparisons may be incomplete: %s", exc
        )
        return pd.DataFrame(columns=_FX_COLUMNS)

    rows: list[dict[str, object]] = []
    for date_str, day_rates in raw.items():
        obs_date = pd.Timestamp(date_str).normalize()
        for currency, rate in day_rates.items():
            rows.append(
                {
                    "currency": currency,
                    "date": obs_date,
                    "rate_usd_to_local": rate,
                }
            )
    return pd.DataFrame(rows, columns=_FX_COLUMNS)


def build_fx_table(
    df: pd.DataFrame,
    cache_path: Path = DEFAULT_FX_CACHE,
) -> pd.DataFrame:
    """Return a daily FX table with prior-rate forward fill."""
    if df.empty or "currency" not in df.columns or "observation_date" not in df.columns:
        return pd.DataFrame(
            columns=["currency", "observation_date", "fx_rate", "fx_rate_date"]
        )

    work = df.copy()
    work["observation_date"] = pd.to_datetime(
        work["observation_date"], errors="coerce"
    ).dt.normalize()
    work = work[work["observation_date"].notna()].copy()
    currencies = sorted(
        {str(v) for v in work["currency"].dropna().unique() if str(v) != "USD"}
    )
    if not currencies:
        return pd.DataFrame(
            columns=["currency", "observation_date", "fx_rate", "fx_rate_date"]
        )

    start_date = work["observation_date"].min()
    end_date = work["observation_date"].max()

    full_cache = _load_cache(cache_path)
    cache = full_cache[full_cache["currency"].isin(currencies)].copy()
    expected_dates = pd.date_range(start_date, end_date, freq="D").normalize()
    expected_set = set(expected_dates)
    missing_dates: set[pd.Timestamp] = set()
    if cache.empty:
        missing_dates = set(expected_set)
    else:
        for currency in currencies:
            have = set(cache.loc[cache["currency"] == currency, "date"])
            missing_dates.update(expected_set - have)
    if missing_dates:
        fetch_start = min(missing_dates)
        fetch_end = max(missing_dates)
        fetched = _fetch_missing_rates(currencies, fetch_start, fetch_end)
        if not fetched.empty:
            cache = pd.concat([cache, fetched], ignore_index=True)
            cache = cache.drop_duplicates(subset=["currency", "date"], keep="last")
            # Merge new rates back into full cache (preserve other currencies)
            other = full_cache[~full_cache["currency"].isin(currencies)]
            full_cache = pd.concat([other, cache], ignore_index=True)
            full_cache = full_cache.drop_duplicates(
                subset=["currency", "date"], keep="last"
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            full_cache.sort_values(["currency", "date"]).to_csv(cache_path, index=False)

    filled: list[pd.DataFrame] = []
    for currency in currencies:
        curr = cache[cache["currency"] == currency][
            ["date", "rate_usd_to_local"]
        ].copy()
        fill_start = start_date
        if not curr.empty:
            fill_start = min(start_date, curr["date"].min())
        all_dates = pd.date_range(fill_start, end_date, freq="D")
        base = pd.DataFrame({"observation_date": all_dates})
        base["currency"] = currency
        if curr.empty:
            base["fx_rate"] = pd.NA
            base["fx_rate_date"] = pd.NaT
        else:
            curr = curr.rename(
                columns={"date": "observation_date", "rate_usd_to_local": "fx_rate"}
            )
            curr["currency"] = currency
            curr["fx_rate_date"] = curr["observation_date"]
            base = base.merge(curr, on=["currency", "observation_date"], how="left")
            base["fx_rate"] = base["fx_rate"].ffill()
            base["fx_rate_date"] = pd.to_datetime(
                base["fx_rate_date"], errors="coerce"
            ).ffill()
        filled.append(base[base["observation_date"] >= start_date].copy())

    return pd.concat(filled, ignore_index=True) if filled else pd.DataFrame()


def attach_fx_and_usd(
    df: pd.DataFrame,
    cache_path: Path = DEFAULT_FX_CACHE,
) -> pd.DataFrame:
    """Attach FX rates, logging warnings for missing same-day FX."""
    if df.empty:
        return df.copy()

    work = df.copy()
    work["observation_date"] = pd.to_datetime(
        work["observation_date"], errors="coerce"
    ).dt.normalize()
    work["price_local"] = pd.to_numeric(work["price_local"], errors="coerce")
    work["fx_rate"] = pd.NA
    work["fx_rate_date"] = pd.NaT
    work["price_usd"] = pd.NA

    usd_mask = work["currency"].eq("USD")
    work.loc[usd_mask, "fx_rate"] = 1.0
    work.loc[usd_mask, "fx_rate_date"] = work.loc[usd_mask, "observation_date"]
    work.loc[usd_mask, "price_usd"] = work.loc[usd_mask, "price_local"]

    fx_table = build_fx_table(work[~usd_mask], cache_path=cache_path)
    if not fx_table.empty:
        work = work.merge(
            fx_table,
            on=["currency", "observation_date"],
            how="left",
            suffixes=("", "_filled"),
        )
        filled_rate = work.pop("fx_rate_filled")
        filled_rate_date = work.pop("fx_rate_date_filled")
        rate_mask = work["fx_rate"].isna()
        rate_date_mask = work["fx_rate_date"].isna()
        work.loc[rate_mask, "fx_rate"] = filled_rate[rate_mask]
        work.loc[rate_date_mask, "fx_rate_date"] = filled_rate_date[rate_date_mask]

    missing = work[~usd_mask & work["fx_rate"].isna()][
        ["currency", "observation_date"]
    ].drop_duplicates()
    for row in missing.itertuples(index=False):
        logger.warning(
            "Missing FX history for %s on %s; USD price left blank",
            row.currency,
            row.observation_date.date(),
        )

    fallback = work[
        ~usd_mask
        & work["fx_rate"].notna()
        & (
            pd.to_datetime(work["fx_rate_date"], errors="coerce")
            < work["observation_date"]
        )
    ][["currency", "observation_date", "fx_rate_date"]].drop_duplicates()
    for row in fallback.itertuples(index=False):
        logger.warning(
            "Missing same-day FX for %s on %s; using prior rate from %s",
            row.currency,
            row.observation_date.date(),
            pd.Timestamp(row.fx_rate_date).date(),
        )

    convert_mask = ~usd_mask & work["fx_rate"].notna() & work["price_local"].notna()
    work.loc[convert_mask, "price_usd"] = (
        work.loc[convert_mask, "price_local"] / work.loc[convert_mask, "fx_rate"]
    )
    return work
