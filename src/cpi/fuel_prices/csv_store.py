"""CSV helpers for fuel_prices tabular outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .constants import COLUMNS


def load_fuel_csv(path: Path) -> pd.DataFrame:
    """Load a fuel CSV, returning an empty schema-aligned frame if missing."""
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return pd.DataFrame(columns=pd.Index(COLUMNS))


def save_fuel_csv(df: pd.DataFrame, path: Path) -> None:
    """Persist a fuel CSV using the canonical column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df[COLUMNS].to_csv(path, index=False)
    print(f"  Saved {len(df):,} rows -> {path}")
