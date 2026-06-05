"""Validate the enrichment cache is still reachable after the concatenate/prepare cutover.

After the prices pipeline migrates from `all_countries_prices.csv` (legacy,
externally populated) to a rebuilt `raw_prices.csv` (produced by the new
`concatenate` stage), the prepare stage regenerates
`data/prices/_enrich/products_input.parquet` with fresh `input_hash` values.

The cache (`data/prices/_enrich/cache/enrichments.parquet`) keys enrichments
by a `cache_key` derived from `input_hash`. If the new prepare run reproduces
the same `input_hash` for every cached row, the cache survives untouched.

This script makes that survival concrete by:

  1. Reading the existing cache.
  2. Recomputing each cache row's `input_hash` from its stored
     (product_name_original, category, country, currency).
  3. Comparing against the set of `input_hash` values now in
     products_input.parquet.
  4. Reporting match rate and listing orphans (≤25 examples).

It is read-only — no parquet is rewritten.

Usage:
    poetry run python scripts/validate_cache_against_new_products_input.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.versioning import input_hash  # noqa: E402


def _row_dict(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name_original"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def main() -> int:
    if not config.ENRICHMENTS_PARQUET.exists():
        print(f"missing {config.ENRICHMENTS_PARQUET}", file=sys.stderr)
        return 1
    if not config.PRODUCTS_INPUT_PARQUET.exists():
        print(
            f"missing {config.PRODUCTS_INPUT_PARQUET} — run "
            "`po prices process --stage prepare` first",
            file=sys.stderr,
        )
        return 1

    cache = pd.read_parquet(config.ENRICHMENTS_PARQUET)
    pi = pd.read_parquet(config.PRODUCTS_INPUT_PARQUET)
    pi_hashes = set(pi["input_hash"].astype(str))

    print(f"cache rows: {len(cache):,}")
    print(f"products_input rows: {len(pi):,}")
    print(f"products_input unique input_hash: {len(pi_hashes):,}")

    cache_hashes = cache.apply(lambda r: input_hash(_row_dict(r)), axis=1)
    matched = cache_hashes.isin(pi_hashes)
    n_matched = int(matched.sum())
    n_total = len(cache)
    rate = (n_matched / n_total) if n_total else 0.0
    print(f"\nmatched: {n_matched:,} / {n_total:,} ({rate:.2%})")

    if n_matched < n_total:
        orphans = cache[~matched]
        print(f"\n{len(orphans):,} orphans — first 25:")
        cols = ["country", "currency", "product_name_original"]
        print(orphans[cols].head(25).to_string(index=False))

    if rate >= 0.995:
        print("\nOK: ≥99.5% of cache rows are reachable by the new input_hash.")
        return 0
    print(
        f"\nWARN: only {rate:.2%} matched — investigate concatenate/prepare drift "
        "before promoting the new raw_prices.csv."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
