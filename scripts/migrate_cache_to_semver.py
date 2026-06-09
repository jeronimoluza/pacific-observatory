"""One-shot migration: rebuild enrichments cache under PROMPT_SEMVER scheme.

The pre-migration cache_key was sha256(input + prompt_bytes_hash + schema + taxonomy).
The post-migration cache_key is sha256(input + PROMPT_SEMVER + schema + taxonomy).
Without this migration, existing 41k cached rows would not match new cache_keys
and every row would be re-enriched (~83 days at 500 RPD).

This script:
  - renames each row's `prompt_version` (a 12-byte hash) to `prompt_bytes_hash`
  - sets `prompt_semver` = "v1" on every row (retroactive v1 label)
  - sets `trust_level` = "high" on every row that lacks one
  - recomputes `cache_key` using the new scheme
  - writes a `.migrated` sibling for the user to swap manually

Read-only on the original; user moves the `.migrated` file into place when
confident.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.versioning import (  # noqa: E402
    PROMPT_SEMVER,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
    cache_key,
)

INPUT_KEYS = ("product_name_original", "category", "country", "currency")


def _structured_input(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name_original"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def migrate_one(path: Path) -> Path | None:
    if not path.exists():
        print(f"skip: {path} does not exist")
        return None
    df = pd.read_parquet(path)
    if df.empty:
        print(f"skip: {path} is empty")
        return None
    print(f"reading {path}  ({len(df):,} rows)")

    missing = [k for k in INPUT_KEYS if k not in df.columns]
    if missing:
        raise SystemExit(
            f"refusing to migrate: missing required cols {missing} in {path}"
        )

    if "prompt_bytes_hash" not in df.columns:
        df["prompt_bytes_hash"] = df.get("prompt_version", pd.NA)
    if "prompt_semver" not in df.columns:
        df["prompt_semver"] = PROMPT_SEMVER
    else:
        df["prompt_semver"] = df["prompt_semver"].fillna(PROMPT_SEMVER)
    if "trust_level" not in df.columns:
        df["trust_level"] = "high"
    else:
        df["trust_level"] = df["trust_level"].fillna("high")
    if "prompt_version" in df.columns:
        df = df.drop(columns=["prompt_version"])

    df["cache_key"] = df.apply(lambda r: cache_key(_structured_input(r)), axis=1)

    out = path.with_suffix(path.suffix + ".migrated")
    df.to_parquet(out, index=False)

    distinct_keys = df["cache_key"].nunique()
    distinct_hashes = df["prompt_bytes_hash"].nunique(dropna=True)
    print(f"  wrote {out}")
    print(f"  distinct cache_key:        {distinct_keys:,}")
    print(f"  distinct prompt_bytes_hash: {distinct_hashes}")
    if distinct_keys != len(df):
        dup = len(df) - distinct_keys
        print(
            f"  WARN: {dup:,} duplicate cache_keys after recompute (input-tuple collisions). "
            "Inspect before swap."
        )
    return out


def main() -> int:
    print(
        f"PROMPT_SEMVER={PROMPT_SEMVER!r}  SCHEMA_VERSION={SCHEMA_VERSION!r}  "
        f"TAXONOMY_VERSION={TAXONOMY_VERSION!r}"
    )
    print()
    for path in (config.ENRICHMENTS_PARQUET, config.FAILED_PARQUET):
        migrate_one(path)
        print()
    print("Migration files written. Verify, then:")
    print(f"  mv {config.ENRICHMENTS_PARQUET}.migrated {config.ENRICHMENTS_PARQUET}")
    print(f"  mv {config.FAILED_PARQUET}.migrated     {config.FAILED_PARQUET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
