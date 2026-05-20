"""Quantity extraction stage for the COICOP pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .quantity.extraction import extract_quantities
from .utils import get_project_root


def _build_key(df: pd.DataFrame) -> pd.Series:
    return df["url_hash"].astype(str) + "|" + df["date"].astype(str)


def run_quantities(project_root: Path, reextract_all: bool = False) -> None:
    data_dir = project_root / "data" / "prices" / "_enrich"
    cache_path = data_dir / "prepared_cache.parquet"
    quantities_path = data_dir / "quantities.csv"

    if not cache_path.exists():
        raise FileNotFoundError(
            f"Prepared cache not found at {cache_path}. Run load stage first."
        )

    df_cache = pd.read_parquet(cache_path)

    if reextract_all or not quantities_path.exists():
        df_quantities = extract_quantities(
            df_prepared=df_cache, project_root=project_root
        )
        df_quantities.to_csv(quantities_path, index=False, encoding="utf-8")
        print(f"✓ Quantities saved to {quantities_path}")
        return

    existing_columns = pd.read_csv(quantities_path, nrows=0).columns
    if "date" not in existing_columns:
        raise ValueError(
            "Existing quantities.csv is missing 'date'. "
            "Run `poetry run python -m prices.enrich.quantities --reextract-all` "
            "to rebuild with date included."
        )

    df_existing_index = pd.read_csv(quantities_path, usecols=("url_hash", "date"))
    existing_keys = set(_build_key(df_existing_index))
    cache_keys = _build_key(df_cache)
    delta_mask = ~cache_keys.isin(existing_keys)
    df_delta = df_cache[delta_mask].copy()

    if df_delta.empty:
        print("✓ No new rows to extract quantities for.")
        return

    df_quantities_delta = extract_quantities(
        df_prepared=df_delta, project_root=project_root
    )

    df_quantities_delta.to_csv(
        quantities_path,
        mode="a",
        header=False,
        index=False,
        encoding="utf-8",
    )
    print(f"✓ Appended {len(df_quantities_delta)} rows to {quantities_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quantity extraction stage for COICOP pipeline"
    )
    parser.add_argument(
        "--reextract-all",
        action="store_true",
        help="Re-extract quantities for all rows in the prepared cache",
    )

    args = parser.parse_args()
    project_root = get_project_root()

    try:
        run_quantities(project_root, reextract_all=args.reextract_all)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
