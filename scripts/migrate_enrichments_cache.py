"""Migrate the legacy enrichments.parquet to the schema-version-partitioned shape.

Idempotent. Lossless. One-shot per cache version bump.

What changes per row:
  - Adds `input_hash` column (recomputed from the row's structured input).
  - Adds `match_method = "legacy_llm"` (every legacy row came from the LLM tier).
  - Adds `modality = "retail"` (no other modality has run yet).
  - Leaves `cache_key` in place for audit traceability — provenance only.

Where it writes:
  - `data/prices/_enrich/cache/enrichments_v{SCHEMA_VERSION}.parquet`
  - Marker file `data/prices/_enrich/cache/.migrated_v{SCHEMA_VERSION}` prevents re-runs.
  - The legacy `enrichments.parquet` is left untouched (read fallback during transition).

Usage:
    python scripts/migrate_enrichments_cache.py             # migrate the real cache
    python scripts/migrate_enrichments_cache.py --src PATH  # migrate a specific file
    python scripts/migrate_enrichments_cache.py --dry-run   # show what would change

"""

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich.tier_b import cache as enrich_cache  # noqa: E402
from prices.enrich import config  # noqa: E402
from prices.enrich.versioning import SCHEMA_VERSION, input_hash  # noqa: E402


def _structured_input(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name_original"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def migrate(src: Path, dest: Path, marker: Path, dry_run: bool = False) -> dict:
    if marker.exists():
        return {"status": "already_migrated", "marker": str(marker)}
    if not src.exists():
        return {"status": "no_source", "src": str(src)}

    df = pd.read_parquet(src)
    if df.empty:
        return {"status": "empty_source", "src": str(src), "rows": 0}

    required = {"product_name_original", "country", "currency"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"source missing required columns: {missing}")

    if "input_hash" not in df.columns:
        df["input_hash"] = df.apply(lambda r: input_hash(_structured_input(r)), axis=1)

    if "match_method" not in df.columns:
        df["match_method"] = "legacy_llm"
    else:
        df["match_method"] = df["match_method"].fillna("legacy_llm")

    if "modality" not in df.columns:
        df["modality"] = "retail"
    else:
        df["modality"] = df["modality"].fillna("retail")

    n_dupe_keys = int(df["input_hash"].duplicated().sum())

    if dry_run:
        return {
            "status": "dry_run",
            "src": str(src),
            "dest": str(dest),
            "rows": len(df),
            "duplicate_input_hashes": n_dupe_keys,
        }

    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    marker.write_text(f"rows={len(df)}\nsrc={src}\ndest={dest}\n")

    return {
        "status": "migrated",
        "src": str(src),
        "dest": str(dest),
        "rows": len(df),
        "duplicate_input_hashes": n_dupe_keys,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=config.ENRICHMENTS_PARQUET)
    parser.add_argument(
        "--dest",
        type=Path,
        default=enrich_cache._partition_path(SCHEMA_VERSION),
    )
    parser.add_argument(
        "--marker",
        type=Path,
        default=config.CACHE_DIR / f".migrated_v{SCHEMA_VERSION}",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = migrate(args.src, args.dest, args.marker, dry_run=args.dry_run)
    print(result)
    return 0 if result["status"] in {"migrated", "dry_run", "already_migrated"} else 1


if __name__ == "__main__":
    sys.exit(main())
