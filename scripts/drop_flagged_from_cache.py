"""Selectively drop rows from enrichments cache + carry remaining rows forward to current SEMVER.

Used after a PROMPT_SEMVER bump to:
  - remove cache rows whose (country, sub_label_id) is being re-enriched under the new prompt
  - recompute cache_key + stamp prompt_semver = current for surviving rows so
    the dedup lookup in enrich.py still recognizes them
  - preserve prompt_bytes_hash on survivors (historical record of what physical
    prompt bytes generated their content)

Default targets: cambodia/lager + malaysia/lip-balm (the v1→v2 cohort).
Override with --target country/sub_label_id (repeatable).

Writes a `.pruned` sibling; user swaps manually (we never overwrite data/).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.versioning import PROMPT_SEMVER, cache_key  # noqa: E402

DEFAULT_TARGETS = [
    ("cambodia", "lager"),
    ("malaysia", "lip-balm"),
]


def _structured_input(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name_original"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--target",
        action="append",
        metavar="COUNTRY/SUB_LABEL_ID",
        help="Drop rows matching this (country, sub_label_id). Repeatable. "
        "Default: cambodia/lager malaysia/lip-balm",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.target:
        targets = []
        for t in args.target:
            try:
                country, sub_label = t.split("/", 1)
            except ValueError:
                raise SystemExit(f"--target must be COUNTRY/SUB_LABEL_ID, got {t!r}")
            targets.append((country, sub_label))
    else:
        targets = DEFAULT_TARGETS

    path = config.ENRICHMENTS_PARQUET
    if not path.exists():
        raise SystemExit(f"cache not found: {path}")
    df = pd.read_parquet(path)
    n_before = len(df)
    print(f"cache: {path}")
    print(f"  rows before: {n_before:,}")
    print(f"  current PROMPT_SEMVER: {PROMPT_SEMVER!r}")
    print(f"  drop targets: {targets}")

    drop_mask = pd.Series(False, index=df.index)
    for country, sub_label in targets:
        m = (df["country"] == country) & (df["sub_label_id"] == sub_label)
        n = int(m.sum())
        print(f"    {country}/{sub_label}: {n} rows")
        drop_mask |= m

    survivors = df[~drop_mask].copy()
    n_after = len(survivors)
    n_dropped = n_before - n_after
    print(f"  rows dropped: {n_dropped:,}")
    print(f"  rows surviving: {n_after:,}")

    if n_dropped == 0:
        print("nothing to drop; aborting.")
        return 1

    survivors["prompt_semver"] = PROMPT_SEMVER
    survivors["cache_key"] = survivors.apply(
        lambda r: cache_key(_structured_input(r)), axis=1
    )
    distinct_keys = survivors["cache_key"].nunique()
    if distinct_keys != n_after:
        print(
            f"  WARN: {n_after - distinct_keys} duplicate cache_keys after recompute "
            "(input-tuple collisions). Inspect before swap."
        )

    out = path.with_suffix(path.suffix + ".pruned")
    survivors.to_parquet(out, index=False)
    print(f"  wrote {out}")
    print()
    print("Verify, then:")
    print(f"  mv {out} {path}")
    print(
        "Then run `po prices enrich` — the dropped rows will cache-miss and re-enrich under v2."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
