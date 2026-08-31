"""Merge the Aug-19 name universe with names the live collect has added since.

    PYTHONPATH=src python src/prices/enrich/gpu/build_universe.py --out <path>

Buckets are recomputed from scratch with embed_store.bucket_of, not carried over,
and checked against the stored column: the partition is only safe to split across
pods if a name's bucket is a pure function of the name.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from prices.enrich.classifier import embed_store

TEMPLATE = Path("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo")
SPLIT = TEMPLATE / "data/prices/_enrich/transfer/embed_names_split_20260819.parquet"
COL = "product_name_original"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", required=True, help="parquet of names found since")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    base = pd.read_parquet(SPLIT, columns=[COL, "bucket"])
    print(f"base   : {len(base):,} rows from {SPLIT.name}")

    # the base file's own bucket column is the reference: recompute and compare
    recomputed = base[COL].astype(str).map(embed_store.bucket_of)
    mismatch = int((recomputed != base["bucket"]).sum())
    print(f"bucket recompute vs stored column: {mismatch} mismatches")
    if mismatch:
        raise SystemExit("bucket_of is not reproducing the stored partition - stop")

    delta = pd.read_parquet(a.delta, columns=[COL])
    print(f"delta  : {len(delta):,} rows from {Path(a.delta).name}")

    names = pd.concat([base[[COL]], delta], ignore_index=True)
    names[COL] = names[COL].astype(str)
    before = len(names)
    names = names.drop_duplicates(subset=[COL], ignore_index=True)
    print(
        f"merged : {before:,} -> {len(names):,} unique ({before - len(names):,} dupes dropped)"
    )

    names["bucket"] = names[COL].map(embed_store.bucket_of)

    assert names[COL].is_unique, "names are not unique"
    assert names[COL].str.len().gt(0).all(), "empty name present"
    assert names["bucket"].between(0, 255).all(), "bucket out of range"
    # every base name keeps the bucket it already had, so vectors already stored
    # under that bucket stay findable
    merged = names.merge(base, on=COL, how="inner", suffixes=("", "_old"))
    assert (
        merged["bucket"] == merged["bucket_old"]
    ).all(), "a base name changed bucket"
    print(
        f"checks : unique OK, buckets 0-255 OK, {len(merged):,} base names kept their bucket"
    )

    counts = names["bucket"].value_counts()
    print(
        f"spread : {counts.min():,} to {counts.max():,} names per bucket "
        f"(mean {counts.mean():,.0f})"
    )

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    names.to_parquet(out, index=False)
    print(
        f"\nwrote  : {len(names):,} names -> {out} ({out.stat().st_size / 1e6:.1f} MB)"
    )


if __name__ == "__main__":
    main()
