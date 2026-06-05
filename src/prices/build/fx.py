"""Thin FX wrapper for prices build.

Reuses src/fuel/fx.attach_fx_and_usd with a prices-owned cache file so
the fuel and prices pipelines do not contend on the same CSV.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from fuel.fx import attach_fx_and_usd as _attach

REPO_ROOT = Path(__file__).resolve().parents[3]
PRICES_FX_CACHE = REPO_ROOT / "data" / "prices" / "_fx" / "fx_cache.csv"


def attach_fx_and_usd(df: pd.DataFrame, cache_path: Path = PRICES_FX_CACHE) -> pd.DataFrame:
    """Wrapper around fuel.fx.attach_fx_and_usd using the prices cache."""
    return _attach(df, cache_path=cache_path)
