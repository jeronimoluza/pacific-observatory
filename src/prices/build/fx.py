"""Thin FX wrapper for prices build.

Reuses src/fuel/fx.attach_fx_and_usd with a prices-owned cache file so
the fuel and prices pipelines do not contend on the same CSV. Adds two
prices-only behaviors on top of the fuel primitive (fuel is left untouched):
input currency normalization (e.g. ``FJ`` -> ``FJD``) and a latest-rate
fallback so rows with a NaT/unmatched observation_date still get a USD value.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cpi.analysis.core import forex
from fuel.fx import _load_cache
from fuel.fx import attach_fx_and_usd as _attach

REPO_ROOT = Path(__file__).resolve().parents[3]
PRICES_FX_CACHE = REPO_ROOT / "data" / "prices" / "_fx" / "fx_cache.csv"


def _normalize_currency_safe(code):
    """Map data currency codes to ISO 4217 where known; leave ISO codes as-is."""
    if not isinstance(code, str):
        return code
    stripped = code.strip()
    if not stripped:
        return code
    try:
        return forex.normalize_currency(stripped)
    except KeyError:
        return stripped.upper()


def _fill_from_latest_rate(out: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    """Fill still-null price_usd rows using each currency's most-recent cached rate."""
    if out.empty or "price_usd" not in out.columns:
        return out
    missing = out["price_usd"].isna()
    if not missing.any():
        return out

    cache = _load_cache(Path(cache_path))
    if cache.empty:
        return out

    latest = cache.sort_values("date").groupby("currency")["rate_usd_to_local"].last()
    price_local = pd.to_numeric(out["price_local"], errors="coerce")
    for currency, rate in latest.items():
        if pd.isna(rate) or rate == 0:
            continue
        mask = missing & out["currency"].eq(currency) & price_local.notna()
        if not mask.any():
            continue
        out.loc[mask, "fx_rate"] = rate
        out.loc[mask, "price_usd"] = price_local[mask] / rate
    return out


def attach_fx_and_usd(
    df: pd.DataFrame, cache_path: Path = PRICES_FX_CACHE
) -> pd.DataFrame:
    """Wrapper around fuel.fx.attach_fx_and_usd using the prices cache.

    Normalizes the input ``currency`` column to ISO 4217 before conversion,
    delegates the date-keyed FX attach to the fuel primitive, then fills any
    remaining null price_usd rows from the currency's latest cached rate.
    """
    work = df.copy()
    if "currency" in work.columns:
        work["currency"] = work["currency"].map(_normalize_currency_safe)
    if "observation_date" in work.columns:
        # Raw scrape dates carry a UTC offset (tz-aware); the FX cache is
        # tz-naive. The FX join is date-only, so drop the tz to a naive UTC
        # date before delegating to the (tz-naive) fuel primitive.
        obs = pd.to_datetime(work["observation_date"], errors="coerce", utc=True)
        work["observation_date"] = obs.dt.tz_localize(None)
    out = _attach(work, cache_path=cache_path)
    return _fill_from_latest_rate(out, cache_path)
