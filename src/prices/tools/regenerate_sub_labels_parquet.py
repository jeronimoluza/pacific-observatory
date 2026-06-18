"""Export the sub-label store → _sub_labels.parquet.

The sub-label store `keywords/coicop/_sub_labels_store.json` is the source of
truth for the sub-label vocabulary (anchors + synonyms with allowed_bases and
5-digit numeric_id granularity), read via `keywords._registry`. The parquet at
keywords/coicop/_sub_labels.parquet is a derived artifact read by tier-b at
index-build time (see src/prices/enrich/index.py:_load_anchors).

Schema preserved for backward compatibility with the existing parquet:
  coicop_code, id, label, lang, role

`coicop_code` is the SubLabel.numeric_id when present (preserving 5-digit
granularity for class 01 items), otherwise the parent 4-digit leaf code.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from prices.enrich.keywords import _registry as registry

_DEFAULT_OUT = (
    Path(__file__).resolve().parents[1]
    / "enrich"
    / "keywords"
    / "coicop"
    / "_sub_labels.parquet"
)

_CLASS_CODES = tuple(f"{i:02d}" for i in range(1, 16))


def build_df() -> pd.DataFrame:
    rows = []
    for cc in _CLASS_CODES:
        sub_table = registry._load_sub_labels_for(cc)
        for leaf_code, sub_labels in sub_table.items():
            for sl in sub_labels:
                code = sl.numeric_id or leaf_code
                for lang, labels in sl.keywords_by_lang.items():
                    for label in labels:
                        rows.append(
                            {
                                "coicop_code": code,
                                "id": sl.id,
                                "label": label,
                                "lang": lang,
                                "role": sl.role,
                            }
                        )
    if not rows:
        return pd.DataFrame(columns=["coicop_code", "id", "label", "lang", "role"])
    df = pd.DataFrame(rows, columns=["coicop_code", "id", "label", "lang", "role"])
    df = df.drop_duplicates(subset=["coicop_code", "id", "label", "lang", "role"])
    df = df.sort_values(
        ["coicop_code", "role", "lang", "label"], kind="stable"
    ).reset_index(drop=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export c{NN}_subs.py → _sub_labels.parquet (source of truth: Python)"
    )
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail with diff summary if on-disk parquet differs from regenerated.",
    )
    args = parser.parse_args()

    df = build_df()
    if args.check:
        if not args.out.exists():
            print(f"{args.out} missing on disk")
            raise SystemExit(1)
        on_disk = pd.read_parquet(args.out)
        key_cols = ["coicop_code", "id", "label", "lang", "role"]
        on_keys = set(map(tuple, on_disk[key_cols].astype(str).itertuples(index=False)))
        new_keys = set(map(tuple, df[key_cols].astype(str).itertuples(index=False)))
        if on_keys == new_keys:
            print(f"OK: on-disk parquet matches c{{NN}}_subs.py ({len(df)} rows)")
            return
        only_disk = on_keys - new_keys
        only_new = new_keys - on_keys
        print(
            f"DIFF: on-disk={len(on_disk)}, regenerated={len(df)}, "
            f"only_on_disk={len(only_disk)}, only_regenerated={len(only_new)}"
        )
        raise SystemExit(1)

    args.out.write_bytes(
        b""
    )  # truncate first so a permission error surfaces immediately
    df.to_parquet(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out}")


if __name__ == "__main__":
    main()
