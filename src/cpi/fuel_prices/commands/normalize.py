"""Normalization commands for fuel_prices."""

from __future__ import annotations

from ..constants import PRIMARY_CSV
from ..csv_store import load_fuel_csv, save_fuel_csv
from ..fixes import run_all_fixes


def cmd_normalize(args) -> None:
    """Apply targeted data-quality fixes to the legacy primary CSV."""
    del args
    df = load_fuel_csv(PRIMARY_CSV)
    if df.empty:
        print("Primary CSV is empty or does not exist.")
        return

    print(f"Loaded {len(df):,} rows from {PRIMARY_CSV}")
    df_fixed = run_all_fixes(df)
    added = len(df_fixed) - len(df)
    save_fuel_csv(df_fixed, PRIMARY_CSV)
    print(f"Normalization complete ({added:+d} rows).")
