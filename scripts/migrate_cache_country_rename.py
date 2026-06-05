"""One-shot: rename two country labels in cache.parquet to match new taxonomy.

After the concatenate stage adopts the on-disk WB country names, two cache
labels diverge from products_input.parquet:

    cache         →  products_input
    taiwan        →  taiwan_china
    hong_kong     →  hong_kong_sar_china

This rewrites every affected cache row's `country` column and recomputes both
`cache_key` (versions: current PROMPT/SCHEMA/TAXONOMY) and the implicit
`input_hash` (not stored on the cache row, but derivable). Writes alongside as
`enrichments.parquet.migrated`; the user swaps manually — we never overwrite
data/.

Usage:
    poetry run python scripts/migrate_cache_country_rename.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.versioning import cache_key, input_hash  # noqa: E402

RENAMES = {
    "taiwan": "taiwan_china",
    "hong_kong": "hong_kong_sar_china",
}


def _structured_input(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name_original"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def main() -> int:
    src = config.ENRICHMENTS_PARQUET
    if not src.exists():
        print(f"missing {src}", file=sys.stderr)
        return 1
    pi_path = config.PRODUCTS_INPUT_PARQUET
    if not pi_path.exists():
        print(
            f"missing {pi_path} — run `po prices process --stage prepare` first",
            file=sys.stderr,
        )
        return 1

    cache = pd.read_parquet(src)
    n_renamed = int(cache["country"].isin(RENAMES).sum())
    print(f"cache rows: {len(cache):,}")
    print(f"rows to rename: {n_renamed:,}")
    if n_renamed == 0:
        print("nothing to migrate — exiting.")
        return 0

    cache = cache.copy()
    cache["country"] = cache["country"].replace(RENAMES)
    cache["cache_key"] = cache.apply(lambda r: cache_key(_structured_input(r)), axis=1)

    pi_hashes = set(pd.read_parquet(pi_path)["input_hash"].astype(str))
    new_hashes = cache.apply(lambda r: input_hash(_structured_input(r)), axis=1)
    matched = new_hashes.isin(pi_hashes)
    rate = matched.mean()
    print(
        f"post-migration input_hash match vs PI: {matched.sum():,} / {len(cache):,} ({rate:.2%})"
    )

    if rate < 0.995:
        print(
            f"WARN: only {rate:.2%} reachable after rename — investigate before swap.",
            file=sys.stderr,
        )

    out = src.with_suffix(src.suffix + ".migrated")
    cache.to_parquet(out, index=False)
    print(f"\nWrote {out}")
    print("Swap manually:")
    print(f"  mv {src} {src}.pre-migrate")
    print(f"  mv {out} {src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
