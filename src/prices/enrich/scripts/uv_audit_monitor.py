"""Unit-value audit monitor -- READ half only (Layer-2).

Reads the built basket parquets (snapshot + observations), which carry the
Layer-2 columns written by build.unit_value_audit.flag_uv_outliers, and emits
the outlier rows for human triage. An outlier flags a ROW, not a cause: the
triage question is whether the unit_value is wrong because of a bad PARSE
(look at pricing_basis / amount_value) or a bad CLASSIFY (look at
product_name_original vs the cell). This monitor lays those columns side by
side so a human can decide; it never mutates the build outputs.

Run:
    PYTHONPATH=src <venv>/bin/python src/prices/enrich/scripts/uv_audit_monitor.py
"""
from __future__ import annotations

import pandas as pd

from prices.build.aggregate import OBSERVATIONS_PARQUET, SNAPSHOT_PARQUET
from prices.enrich import config

OUT_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "_monitor"

TRIAGE_COLS = [
    "coicop_code",
    "country",
    "uv_cell_n",
    "product_name_original",
    "unit_value_local",
    "pricing_basis",
    "amount_value",
    "count",
    "multiplier",
    "coicop_code",
    "uv_robust_z",
    "observation_date",
    "source",
]


def _load_built() -> pd.DataFrame:
    pieces = []
    for path in (SNAPSHOT_PARQUET, OBSERVATIONS_PARQUET):
        if path.exists():
            df = pd.read_parquet(path)
            df["_build"] = path.stem
            pieces.append(df)
    if not pieces:
        raise RuntimeError(
            "No build parquets found -- run `prices build` before the monitor."
        )
    return pd.concat(pieces, ignore_index=True)


def main() -> None:
    df = _load_built()
    if "trust_uv" not in df.columns:
        raise RuntimeError(
            "Built parquets predate Layer-2 -- rebuild with flag_uv_outliers wired."
        )

    total = len(df)
    outliers = df[df["uv_outlier"]].copy()
    thin = int((df["trust_uv"] == "flag").sum()) - len(outliers)

    cell_med = (
        df[df["trust_uv"] == "high"]
        .groupby(["coicop_code", "country"])["unit_value_local"]
        .median()
        .rename("cell_median_uv")
    )
    outliers = outliers.merge(cell_med, on=["coicop_code", "country"], how="left")

    keep = [c for c in TRIAGE_COLS if c in outliers.columns] + [
        "cell_median_uv",
        "_build",
    ]
    out = outliers[keep].sort_values(
        ["coicop_code", "country", "uv_robust_z"], ascending=[True, True, False]
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "uv_outlier_candidates.csv"
    out.to_csv(out_csv, index=False)

    print("rows (snapshot + observations):", total)
    print("uv_outlier rows:", len(outliers))
    print("thin-cell (flag, not outlier) rows:", thin)
    print(
        "distinct outlier cells:",
        out[["coicop_code", "country"]].drop_duplicates().shape[0],
    )
    print("wrote", out_csv)


if __name__ == "__main__":
    main()
