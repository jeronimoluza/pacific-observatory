#!/usr/bin/env python3
"""Split the legacy 500-row gold by provenance into a working gold and a raw held-out set.

Additive and idempotent: reads the legacy gold READ-ONLY and writes two new
parquets under data/prices/enrich/gold/. The legacy file at
data/prices/_enrich/gold_labels.parquet is NEVER opened for write and NEVER
touched. Re-running reproduces byte-identical partitions.

Provenance predicate (NOT a magic count — see Phase 0 RESEARCH "Pitfall 5"):
  holdout (cache-verbatim) = source_set == "v3" AND labeler_notes is empty   (~187)
  working                  = source_set == "new"
                             OR (source_set == "v3" AND labeler_notes != "")  (~313)

The held-out set is written WITH labels intact (named *_raw); Plan 03 strips
and blind-relabels it into holdout_cert.parquet.

DATA SAFETY: this script writes under data/. Per CLAUDE.md, Claude does NOT run
it — the USER runs `poetry run python scripts/split_gold.py` from the repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

# Legacy gold — opened READ-ONLY only.
SRC = REPO_ROOT / "data" / "prices" / "_enrich" / "gold_labels.parquet"

# Canonical destination for the de-contaminated split.
DST_DIR = REPO_ROOT / "data" / "prices" / "enrich" / "gold"
WORKING_OUT = DST_DIR / "gold_labels.parquet"
HOLDOUT_OUT = DST_DIR / "holdout_cert_raw.parquet"


def main() -> None:
    if not SRC.exists():
        sys.exit(
            f"ERROR: legacy gold not found at {SRC}\n"
            "Cannot split. This script reads the legacy gold read-only; it does "
            "not create it. Restore the legacy gold first."
        )

    df = pd.read_parquet(SRC)

    notes = df["labeler_notes"].fillna("").str.strip()
    is_v3 = df["source_set"] == "v3"

    holdout = df[is_v3 & (notes == "")]
    working = df[(df["source_set"] == "new") | (is_v3 & (notes != ""))]

    # Partition must be exact and disjoint.
    assert len(holdout) + len(working) == len(
        df
    ), f"partition size mismatch: {len(holdout)} + {len(working)} != {len(df)}"
    holdout_ids = set(holdout["row_id"])
    working_ids = set(working["row_id"])
    assert holdout_ids.isdisjoint(
        working_ids
    ), "row_id overlap between holdout and working"
    assert holdout_ids | working_ids == set(
        df["row_id"]
    ), "partition does not cover all row_ids"

    # No cache-verbatim row may leak into the working gold.
    leaked = working[(working["source_set"] == "v3") & (notes.loc[working.index] == "")]
    assert len(leaked) == 0, (
        f"{len(leaked)} cache-verbatim row(s) leaked into working gold "
        "(source_set=='v3' with empty labeler_notes)"
    )

    DST_DIR.mkdir(parents=True, exist_ok=True)
    working.to_parquet(WORKING_OUT, index=False)
    holdout.to_parquet(HOLDOUT_OUT, index=False)

    print(f"working={len(working)} holdout={len(holdout)}")
    print(f"  wrote {WORKING_OUT.relative_to(REPO_ROOT)} ({len(working)} rows)")
    print(
        f"  wrote {HOLDOUT_OUT.relative_to(REPO_ROOT)} ({len(holdout)} rows, labels intact)"
    )
    print(f"  legacy source untouched: {SRC.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
