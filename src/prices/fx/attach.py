"""Attach FX rates and USD prices to observation rows. **Offline.**

This is a port of ``fuel.fx``'s date-keyed attach with one deliberate
difference: it never fetches. The fuel primitive refetches whenever it finds a
missing date and rewrites the shared CSV in place, which is both a network
dependency inside the build and the cause of the interleaved-cache corruption
that fires when several regions build in parallel. Refresh is a separate,
explicit step (:mod:`prices.fx.refresh`); the build and the render read the
cache and nothing else.

Public behaviour of :func:`attach_fx_and_usd` is unchanged from
``prices.build.fx``: same signature, same columns, same conversion.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from prices.fx.aliases import normalize_currency_safe
from prices.fx.audit import flag_rate_outliers
from prices.fx.cache import load_cache
from prices.fx.paths import PRICES_FX_CACHE

logger = logging.getLogger(__name__)

_FX_TABLE_COLUMNS = ["currency", "observation_date", "fx_rate", "fx_rate_date"]


def build_fx_table(
    df: pd.DataFrame,
    cache_path: Path = PRICES_FX_CACHE,
) -> pd.DataFrame:
    """Daily FX table for the currencies in ``df``, with prior-rate forward fill.

    Weekend and thin-currency gaps are covered by carrying the previous
    published rate forward, and ``fx_rate_date`` records which day the rate
    actually came from so a stale conversion stays visible.
    """
    if df.empty or "currency" not in df.columns or "observation_date" not in df.columns:
        return pd.DataFrame(columns=_FX_TABLE_COLUMNS)

    work = df.copy()
    work["observation_date"] = pd.to_datetime(
        work["observation_date"], errors="coerce"
    ).dt.normalize()
    work = work[work["observation_date"].notna()]
    currencies = sorted(
        {str(v) for v in work["currency"].dropna().unique() if str(v) != "USD"}
    )
    if not currencies:
        return pd.DataFrame(columns=_FX_TABLE_COLUMNS)

    start_date = work["observation_date"].min()
    end_date = work["observation_date"].max()

    cache = load_cache(Path(cache_path))
    cache = cache[cache["currency"].isin(currencies)]

    filled: list[pd.DataFrame] = []
    for currency in currencies:
        curr = cache[cache["currency"] == currency][["date", "rate_usd_to_local"]]
        fill_start = start_date if curr.empty else min(start_date, curr["date"].min())
        base = pd.DataFrame(
            {"observation_date": pd.date_range(fill_start, end_date, freq="D")}
        )
        base["currency"] = currency
        if curr.empty:
            base["fx_rate"] = pd.NA
            base["fx_rate_date"] = pd.NaT
        else:
            curr = curr.rename(
                columns={"date": "observation_date", "rate_usd_to_local": "fx_rate"}
            )
            curr = curr.assign(currency=currency, fx_rate_date=curr["observation_date"])
            base = base.merge(curr, on=["currency", "observation_date"], how="left")
            base["fx_rate"] = base["fx_rate"].ffill()
            base["fx_rate_date"] = pd.to_datetime(
                base["fx_rate_date"], errors="coerce"
            ).ffill()
        filled.append(base[base["observation_date"] >= start_date])

    return (
        pd.concat(filled, ignore_index=True)
        if filled
        else pd.DataFrame(columns=_FX_TABLE_COLUMNS)
    )


def _fill_from_latest_rate(out: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    """Fill still-null ``price_usd`` from each currency's most-recent rate.

    **Floored per currency at that currency's earliest cached rate.** Before
    the corpus reached back to 2013 every row was recent, so "latest rate" was
    a fair stand-in for a missing day. Over a 13-year corpus it is not: a row
    predating the currency's first cached rate would be converted at today's
    rate, and the error scales with how much the currency moved in between --
    so it is worst exactly where it is least visible. VES coverage starts
    2018-05-29 and Venezuela redenominated, so a 2017 bolivar priced at the
    2026 rate is wrong by orders of magnitude across 40,877 products. MRU
    (2018) and XCG (2025) have the same shape.

    NaT dates fail the comparison and are therefore left null too: an undated
    row cannot be checked against the currency's coverage window. A null
    ``price_usd`` is recoverable downstream; a plausible wrong one is not.
    """
    if out.empty or "price_usd" not in out.columns:
        return out
    missing = out["price_usd"].isna()
    if not missing.any():
        return out

    cache = load_cache(Path(cache_path))
    if cache.empty:
        return out

    ordered = cache.sort_values("date")
    latest = ordered.groupby("currency")["rate_usd_to_local"].last()
    earliest_date = ordered.groupby("currency")["date"].first()
    obs = pd.to_datetime(out.get("observation_date"), errors="coerce")
    price_local = pd.to_numeric(out["price_local"], errors="coerce")

    for currency, rate in latest.items():
        if pd.isna(rate) or rate == 0:
            continue
        mask = missing & out["currency"].eq(currency) & price_local.notna()
        floor = earliest_date.get(currency)
        if floor is not None and not pd.isna(floor):
            mask = mask & obs.notna() & (obs >= floor)
        if not mask.any():
            continue
        out.loc[mask, "fx_rate"] = rate
        out.loc[mask, "price_usd"] = price_local[mask] / rate
    return out


def _mark_suspect_rates(out: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    """Add ``fx_suspect``: the rate used is implausible for that currency.

    Computed once per build from the cache, then joined on
    ``(currency, fx_rate_date)`` -- the day the rate actually came from, not
    the observation day, so a forward-filled contaminated rate is caught too.
    See :mod:`prices.fx.audit` for what "implausible" means and what it
    deliberately does not catch.
    """
    out["fx_suspect"] = False
    cache = load_cache(Path(cache_path))
    if cache.empty or "fx_rate_date" not in out.columns:
        return out
    suspect = cache[flag_rate_outliers(cache)]
    if suspect.empty:
        return out

    keys = suspect[["currency", "date"]].drop_duplicates()
    keys["fx_suspect_join"] = True
    rate_date = pd.to_datetime(out["fx_rate_date"], errors="coerce").dt.normalize()
    probe = pd.DataFrame(
        {"currency": out["currency"].to_numpy(), "date": rate_date.to_numpy()}
    )
    merged = probe.merge(
        keys.rename(columns={"date": "date"}), on=["currency", "date"], how="left"
    )
    # notna() rather than fillna(False): the join column is True-or-missing,
    # and fillna on an object column is deprecated.
    out["fx_suspect"] = merged["fx_suspect_join"].notna().to_numpy()

    if out["fx_suspect"].any():
        hit = out.loc[out["fx_suspect"], ["currency", "fx_rate_date"]].drop_duplicates()
        logger.warning(
            "Implausible FX rate for %s currency-days; %s rows left unconverted",
            len(hit),
            int(out["fx_suspect"].sum()),
        )
    return out


def attach_fx_and_usd(
    df: pd.DataFrame, cache_path: Path = PRICES_FX_CACHE
) -> pd.DataFrame:
    """Attach ``fx_rate``, ``fx_rate_date``, ``price_usd`` to observation rows.

    Normalises the ``currency`` column to ISO 4217, does the date-keyed FX
    join with prior-rate forward fill, then fills any remaining null
    ``price_usd`` from the currency's latest cached rate (floored per
    currency). Adds ``fx_suspect`` marking rows whose rate is implausible.

    Never touches the network.
    """
    if df.empty:
        return df.copy()

    work = df.copy()
    if "currency" in work.columns:
        work["currency"] = work["currency"].map(normalize_currency_safe)
    if "observation_date" in work.columns:
        # Raw scrape dates carry a UTC offset (tz-aware); the FX cache is
        # tz-naive. The FX join is date-only, so drop the tz to a naive UTC
        # date first.
        obs = pd.to_datetime(work["observation_date"], errors="coerce", utc=True)
        work["observation_date"] = obs.dt.tz_localize(None)

    work["observation_date"] = pd.to_datetime(
        work.get("observation_date"), errors="coerce"
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
            row.observation_date.date()
            if pd.notna(row.observation_date)
            else row.observation_date,
        )

    stale = work[
        ~usd_mask
        & work["fx_rate"].notna()
        & (
            pd.to_datetime(work["fx_rate_date"], errors="coerce")
            < work["observation_date"]
        )
    ][["currency", "observation_date", "fx_rate_date"]].drop_duplicates()
    for row in stale.itertuples(index=False):
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

    work = _fill_from_latest_rate(work, cache_path)
    return _mark_suspect_rates(work, cache_path)
