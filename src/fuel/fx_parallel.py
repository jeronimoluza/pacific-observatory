"""Attach the shared parallel-market FX series (``prices.fx.parallel``) to fuel rows."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from prices.fx.parallel import MAX_CARRY, PARALLEL_CACHE, load_parallel


def attach_parallel(
    df: pd.DataFrame, cache_path: Path = PARALLEL_CACHE
) -> pd.DataFrame:
    """Add ``fx_rate_parallel`` and ``price_usd_parallel`` (NaN where none applies)."""
    out = df.copy()
    out["fx_rate_parallel"] = float("nan")
    rates = load_parallel(cache_path)
    if out.empty or rates.empty:
        out["price_usd_parallel"] = float("nan")
        return out
    dates = pd.to_datetime(out["observation_date"], errors="coerce")
    for currency, group in rates.groupby("currency"):
        mask = out["currency"].eq(currency) & dates.notna()
        if not mask.any():
            continue
        left = pd.DataFrame({"date": dates[mask], "_i": out.index[mask]}).sort_values(
            "date"
        )
        matched = pd.merge_asof(
            left,
            group[["date", "rate_usd_to_local"]].sort_values("date"),
            on="date",
            direction="backward",
            tolerance=MAX_CARRY,
        )
        out.loc[matched["_i"], "fx_rate_parallel"] = matched[
            "rate_usd_to_local"
        ].to_numpy()
    out["price_usd_parallel"] = (
        pd.to_numeric(out["price_local"], errors="coerce") / out["fx_rate_parallel"]
    )
    return out
