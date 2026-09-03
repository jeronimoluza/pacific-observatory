"""Diff a build against a captured reference, and say which fix explains each change.

A parity check that only reports "3.1M rows differ" is not usable: the whole
point of the reference set is that the new run is EXPECTED to differ, because
twelve commits landed after it was captured. What matters is whether every
changed row falls inside a population somebody intended to change.

So each changed row is attributed to exactly one population, first match wins,
and the counts sum to the delta. Anything left over is `unexplained`, and that
number is the actual result: a regression is a changed row nobody can name.

Comparison is column at a time, not frame at a time. The snapshot is 2.8M rows
across 46 columns and two copies of it in pandas will not fit next to a running
build; one column of it is ~20 MB. Parquet is columnar and this is the access
pattern it exists for, so the memory-safe version is also the simple one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Grain of each artifact. The key has to be unique or the row-level diff is
# meaningless, so uniqueness is asserted rather than assumed.
KEYS = {
    "global_prices_snapshot": ("input_hash",),
    "global_prices_unit_value_summary": (
        "period",
        "coicop_code",
        "country",
        "standard_unit",
    ),
    "global_prices_analytical": (
        "country",
        "coicop_code",
        "standard_unit",
        "window_start",
    ),
}

# Derived views with no stable row identity. `observations` explodes the
# snapshot back out over dates and carries no id, so aligning it row-wise would
# mean inventing a key and then diffing an artifact of that invention. Their
# row counts still move for real reasons, so they are counted, not diffed.
COUNTED_ONLY = (
    "global_prices_observations",
    "global_prices_trusted_observations",
)

UV_COLS = (
    "unit_value_local",
    "unit_value_usd",
    "uv_robust_z",
    "uv_cell_n",
    "uv_outlier",
    "uv_thin",
    "trust_uv",
    "qa_uv_category",
    "qa_uv_inlier",
    "qa_uv_thin",
)


def _read_col(path: Path, col: str) -> pd.Series:
    return pq.read_table(path, columns=[col])[col].to_pandas()


def _columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema_arrow.names)


def _key_series(path: Path, key: tuple[str, ...]) -> pd.Series:
    cols = pq.read_table(path, columns=list(key)).to_pandas()
    if len(key) == 1:
        s = cols[key[0]].astype(str)
    else:
        s = cols[list(key)].astype(str).agg("\x1f".join, axis=1)
    if s.duplicated().any():
        n = int(s.duplicated().sum())
        raise ValueError(
            f"{path.name}: {key} is not unique ({n} duplicate keys). "
            "A row-level diff needs a grain key; fix the key before trusting it."
        )
    return s


def _align(ref_path: Path, new_path: Path, key: tuple[str, ...]):
    """Positional index into each file for the keys they share."""
    r = _key_series(ref_path, key)
    n = _key_series(new_path, key)
    r_pos = pd.Series(np.arange(len(r)), index=r.to_numpy())
    n_pos = pd.Series(np.arange(len(n)), index=n.to_numpy())
    common = r_pos.index.intersection(n_pos.index)
    return (
        r_pos.loc[common].to_numpy(),
        n_pos.loc[common].to_numpy(),
        common,
        r_pos.index.difference(n_pos.index),
        n_pos.index.difference(r_pos.index),
    )


def _col_differs(ref: pd.Series, new: pd.Series) -> np.ndarray:
    """Elementwise inequality with NaN == NaN, so a null column is not a delta."""
    if ref.dtype.kind == "f" and new.dtype.kind == "f":
        a, b = ref.to_numpy(float), new.to_numpy(float)
        both_nan = np.isnan(a) & np.isnan(b)
        return ~(both_nan | np.isclose(a, b, rtol=1e-9, atol=0.0, equal_nan=True))
    a = ref.astype(object).where(ref.notna(), None).to_numpy()
    b = new.astype(object).where(new.notna(), None).to_numpy()
    return a != b


def _diff_columns(
    ref_path: Path, new_path: Path, ri: np.ndarray, ni: np.ndarray
) -> dict[str, np.ndarray]:
    """{column: bool mask over the aligned rows}. Columns only on one side are
    reported as schema drift by the caller, not silently skipped."""
    shared = [c for c in _columns(ref_path) if c in set(_columns(new_path))]
    out = {}
    for c in shared:
        d = _col_differs(_read_col(ref_path, c).iloc[ri], _read_col(new_path, c).iloc[ni])
        if d.any():
            out[c] = d
    return out


def _attribute(
    ref_path: Path, ni: np.ndarray, ri: np.ndarray, diffs: dict[str, np.ndarray]
) -> list[tuple[str, np.ndarray]]:
    """The six populations the reference README says the delta should land in.

    Ordered, and first match wins, so the counts partition the changed rows
    instead of overlapping. A row that changed for two reasons is booked under
    the earlier one; the point is to leave nothing unnamed, not to apportion.
    """
    n = len(ri)
    zero = np.zeros(n, dtype=bool)
    touched = lambda *cs: np.logical_or.reduce(  # noqa: E731
        [diffs.get(c, zero) for c in cs] or [zero]
    )

    def ref_col(c):
        return _read_col(ref_path, c).iloc[ri].reset_index(drop=True)

    country = ref_col("country").astype(str).str.lower()
    source = ref_col("source").astype(str)
    name = ref_col("product_name_original").astype(str)
    declared = ref_col("declared_coicop_codes").astype(str)
    ref_date = pd.to_datetime(ref_col("observation_date"), errors="coerce", utc=True)

    return [
        (
            "slovak_slovenian_price",
            country.isin(["slovakia", "slovenia"]).to_numpy()
            & touched("price_local", "price_usd"),
        ),
        (
            "cc_1970_date",
            (ref_date.dt.year == 1970).fillna(False).to_numpy()
            & touched("observation_date"),
        ),
        (
            "mangusa_case_size",
            (source == "mangusa_cw").to_numpy() & touched("count", "multiplier"),
        ),
        (
            "pack_of_n_multipack",
            name.str.contains(r"pack of \d+", case=False, regex=True).to_numpy()
            & touched("count", "multiplier", "is_multipack", "is_bundle"),
        ),
        (
            "non_leaf_declared_coicop",
            (declared.str.len() > 0).to_numpy()
            & (declared.str.lower() != "nan").to_numpy()
            & touched("coicop_code"),
        ),
        # Last on purpose: a uv-only change is the weakest claim, so it only
        # collects rows no sharper population wanted.
        (
            "absolute_uv_gate",
            np.logical_or.reduce([diffs.get(c, zero) for c in UV_COLS])
            & ~np.logical_or.reduce(
                [m for c, m in diffs.items() if c not in UV_COLS] or [zero]
            ),
        ),
    ]


def compare_keyed(ref_path: Path, new_path: Path, key: tuple[str, ...]) -> dict:
    ri, ni, common, only_ref, only_new = _align(ref_path, new_path, key)
    diffs = _diff_columns(ref_path, new_path, ri, ni)
    changed = (
        np.logical_or.reduce(list(diffs.values()))
        if diffs
        else np.zeros(len(ri), dtype=bool)
    )

    populations, claimed = {}, np.zeros(len(ri), dtype=bool)
    if ref_path.name.startswith("global_prices_snapshot") and changed.any():
        for label, mask in _attribute(ref_path, ni, ri, diffs):
            mine = mask & changed & ~claimed
            claimed |= mine
            populations[label] = int(mine.sum())

    ref_cols, new_cols = set(_columns(ref_path)), set(_columns(new_path))
    return {
        "rows_ref": int(len(ri) + len(only_ref)),
        "rows_new": int(len(ni) + len(only_new)),
        "common": int(len(common)),
        "dropped": int(len(only_ref)),
        "added": int(len(only_new)),
        "changed": int(changed.sum()),
        "by_column": {c: int(m.sum()) for c, m in sorted(diffs.items())},
        "populations": populations,
        "unexplained": int((changed & ~claimed).sum()) if populations else None,
        "cols_only_ref": sorted(ref_cols - new_cols),
        "cols_only_new": sorted(new_cols - ref_cols),
    }


def compare(ref_dir: Path, new_dir: Path) -> dict:
    report = {}
    for name, key in KEYS.items():
        r, n = ref_dir / f"{name}.parquet", new_dir / f"{name}.parquet"
        if not r.exists() or not n.exists():
            report[name] = {"skipped": f"missing {'ref' if not r.exists() else 'new'}"}
            continue
        report[name] = compare_keyed(r, n, key)
    for name in COUNTED_ONLY:
        r, n = ref_dir / f"{name}.parquet", new_dir / f"{name}.parquet"
        if not r.exists() or not n.exists():
            report[name] = {"skipped": "missing"}
            continue
        report[name] = {
            "rows_ref": pq.ParquetFile(r).metadata.num_rows,
            "rows_new": pq.ParquetFile(n).metadata.num_rows,
            "note": "no stable row key; counted only",
        }
    return report


def render(report: dict) -> str:
    out = []
    for name, r in report.items():
        out.append(f"== {name}")
        if "skipped" in r:
            out.append(f"   SKIPPED: {r['skipped']}")
            continue
        d = r["rows_new"] - r["rows_ref"]
        out.append(f"   rows: {r['rows_ref']:,} -> {r['rows_new']:,} ({d:+,})")
        if "note" in r:
            out.append(f"   {r['note']}")
            continue
        out.append(
            f"   common={r['common']:,} dropped={r['dropped']:,} "
            f"added={r['added']:,} changed={r['changed']:,}"
        )
        for c in ("cols_only_ref", "cols_only_new"):
            if r[c]:
                out.append(f"   SCHEMA DRIFT {c}: {r[c]}")
        if r["populations"]:
            for label, n in r["populations"].items():
                out.append(f"     {label:.<32} {n:>10,}")
            out.append(f"     {'UNEXPLAINED':.<32} {r['unexplained']:>10,}")
        if r["by_column"]:
            top = sorted(r["by_column"].items(), key=lambda kv: -kv[1])[:12]
            out.append("   top changed columns: " + ", ".join(f"{c}={n:,}" for c, n in top))
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m prices.build.parity <ref_dir> <new_dir>")
        return 2
    print(render(compare(Path(argv[0]), Path(argv[1]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
