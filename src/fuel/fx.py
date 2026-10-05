"""FX helpers for the migrated fuel build stage."""

from __future__ import annotations

import functools
import logging
import os
import time
from pathlib import Path

import pandas as pd

from prices.fx import frankfurter

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# v2 = Frankfurter v2. The old fx_cache.csv mixed providers (and SYP old/new pound).
DEFAULT_FX_CACHE = _PROJECT_ROOT / "data" / "fuel" / "fx_cache_v2.csv"
_FX_COLUMNS = ["currency", "date", "rate_usd_to_local"]
_RATE_LIMITED_BEFORE = pd.Timestamp("2021-01-01")


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


@functools.lru_cache(maxsize=1)
def _provider_coverage() -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """Frankfurter v2 coverage window per currency; empty if unreachable."""
    try:
        served = frankfurter.list_currencies(scope_all=True)
    except Exception as exc:
        logger.warning("FX coverage lookup failed: %s", exc)
        return {}
    return {
        row.iso_code: (row.start_date, row.end_date)
        for row in served.itertuples(index=False)
    }


def _fetch_missing_rates(
    currencies: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    coverage: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
) -> pd.DataFrame:
    accepted, rejected = frankfurter.screen_quotes(currencies, set(coverage))
    if rejected:
        logger.warning("No FX provider coverage for %s; USD left blank", rejected)
    if not accepted:
        return pd.DataFrame(columns=_FX_COLUMNS)
    # Batches of 25 x 2-year windows: one response for ~80 currencies gets
    # truncated (IncompleteRead), and ranges starting before 2021 are limited
    # to 10 requests/minute per IP (429), so those requests are paced.
    accepted.sort(key=lambda c: coverage[c][0])
    frames: list[pd.DataFrame] = []
    try:
        for i in range(0, len(accepted), 25):
            batch = accepted[i : i + 25]
            window_start = max(start_date, coverage[batch[0]][0])
            while window_start <= end_date:
                window_end = min(
                    window_start + pd.DateOffset(years=2) - pd.Timedelta(days=1),
                    end_date,
                )
                frames.append(_fetch_window(batch, window_start, window_end))
                if window_start < _RATE_LIMITED_BEFORE:
                    time.sleep(6.5)
                window_start = window_end + pd.Timedelta(days=1)
    except Exception as exc:
        logger.warning(
            "FX fetch unavailable; USD comparisons may be incomplete: %s", exc
        )
        return pd.DataFrame(columns=_FX_COLUMNS)
    return (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=_FX_COLUMNS)
    )


def _fetch_window(
    batch: list[str], start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    for attempt in range(2):
        try:
            return frankfurter.fetch_rates(
                batch,
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
                chunk_years=100,
            )
        except Exception as exc:
            if attempt:
                raise
            logger.warning(
                "FX window %s..%s failed (%s); retrying in 65s",
                start.date(),
                end.date(),
                exc,
            )
            time.sleep(65)


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
    # Compare spans, not days: the provider skips weekends/holidays (the
    # forward fill below covers those), and dates outside its coverage window
    # can never be served. Either would otherwise force a refetch every build.
    coverage = _provider_coverage()
    missing_dates: set[pd.Timestamp] = set()
    for currency in currencies:
        if currency not in coverage:
            continue
        lo, hi = coverage[currency]
        want_lo = start_date if pd.isna(lo) else max(start_date, lo)
        want_hi = end_date if pd.isna(hi) else min(end_date, hi)
        if want_lo > want_hi:
            continue
        have = cache.loc[cache["currency"] == currency, "date"]
        if have.empty:
            missing_dates.update({want_lo, want_hi})
            continue
        if want_lo < have.min() - pd.Timedelta(days=4):
            missing_dates.update({want_lo, have.min() - pd.Timedelta(days=1)})
        # Listed end dates can run a few days ahead of served rates (XOF).
        if want_hi > have.max() + pd.Timedelta(days=4):
            missing_dates.update({have.max() + pd.Timedelta(days=1), want_hi})
    if missing_dates:
        fetch_start = min(missing_dates)
        fetch_end = max(missing_dates)
        fetched = _fetch_missing_rates(currencies, fetch_start, fetch_end, coverage)
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
            # Write-then-rename so concurrent region builds can't interleave lines.
            tmp_path = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
            full_cache.sort_values(["currency", "date"]).to_csv(tmp_path, index=False)
            os.replace(tmp_path, cache_path)

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
