"""Byte-identity regression harness — YAML extractor vs typed-tree extractor.

Runs `prices.enrich.extract.extract` twice over the same corpus:
  1. baseline: module loads patterns from `static/pack_patterns.yaml` and
     `static/regex_units.yaml` (the on-disk YAML loader).
  2. typed:    module-level pattern dicts are monkey-patched with values
     derived from `prices.enrich.regex_patterns/` (the typed tree).

Compares StructuralFields output across both runs. Per §5.2 the contract is:
  - `pricing_basis`, `standard_unit`, `amount_value`, `count`, `is_multipack`
    must be byte-identical
On any diff, prints the row, the field, both values, and the pattern that fired.
Exit code 0 on full match, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CORPUS = _REPO_ROOT / "data" / "prices" / "_enrich" / "prepared_cache.parquet"

# Fields that must be byte-identical per §5.2.
_COMPARE_FIELDS = (
    "pricing_basis",
    "standard_unit",
    "amount_value",
    "count",
    "is_multipack",
)


def _extract_module():
    from prices.enrich import extract as ex

    return ex


def _normalize_module():
    from prices.enrich import normalize as nm

    return nm


def _typed_dicts() -> dict[str, Any]:
    """Build the same in-memory shape that extract.py's _load_regex_units
    and normalize.py's _load_pack_patterns produce, sourced from the typed tree.
    """
    from prices.enrich.regex_patterns._registry import _INDEX
    from prices.enrich.regex_patterns.unit_tables import UNIT_NORM, UNIT_MAP
    from prices.enrich.regex_patterns.flag_markers import (
        BUNDLE_MARKERS,
        PROMO_MARKERS,
    )

    # Replay the YAML's original list order by id-based grouping. The YAML
    # iterated extra_units, extra_count_markers, multi_pack_markers in source
    # order; we mirror that with explicit orderings sourced from the static
    # files. Pattern files in the typed tree were authored in the same order.
    pack_patterns: list[dict[str, Any]] = []
    extra_units: list[dict[str, Any]] = []
    extra_count: list[dict[str, Any]] = []
    multi_pack: list[dict[str, Any]] = []

    # Globally-unique ids — id determines bucket.
    _CANON_ORDER = (
        "multipack_num_x_value_unit",
        "multipack_value_unit_x_count",
        "multipack_pcs_en",
        "multipack_n_x_only",
        "multipack_vi_loc",
        "multipack_vi_count_unit",
        "multipack_zh_count_unit",
        "multipack_ja_kana_set",
        "value_unit_volume_mass",
        "zh_volume_mass",
    )
    _EXTRA_UNIT_ORDER = ("cl_volume", "vi_lit_volume")
    _EXTRA_COUNT_ORDER = (
        "cjk_mai",
        "cjk_pair",
        "cjk_grain",
        "cjk_strip",
        "cjk_sheet_tissue",
        "cjk_set_group",
        "cjk_numeral_version",
        "cjk_numeral_set",
        "vi_to_sheets",
        "cjk_ko_pcs",
        "cjk_n_x_count",
        "cjk_double_pack",
        "en_caps",
        "en_tablets",
        "en_sachets_s",
        "en_sheets",
        "en_pack_of",
        "en_n_pack",
        "en_n_individual_pack",
        "en_twin_pack",
        "en_triple_pack",
        "en_double_pack",
        "vi_m_pieces",
    )
    _MULTI_PACK_ORDER = ("cjk_inner_outer_star", "cjk_inner_outer_full")

    for pid in _CANON_ORDER:
        pat, _ = _INDEX[pid]
        pack_patterns.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "groups": dict.fromkeys(
                    pat.groups, ""
                ),  # placeholder; not used by extract_pack
            }
        )

    for pid in _EXTRA_UNIT_ORDER:
        pat, _ = _INDEX[pid]
        ue = pat.unit_emit
        extra_units.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "basis": ue.basis,
                "su": ue.su,
                "mul": float(ue.mul),
            }
        )

    for pid in _EXTRA_COUNT_ORDER:
        pat, _ = _INDEX[pid]
        extra_count.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "fixed_count": pat.fixed_count,
            }
        )

    for pid in _MULTI_PACK_ORDER:
        pat, _ = _INDEX[pid]
        multi_pack.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
            }
        )

    def _typed_markers(table: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
        return [
            {
                "lang": lang,
                "patterns": [re.compile(p, flags=re.IGNORECASE) for p in pats],
            }
            for lang, pats in table.items()
        ]

    return {
        "unit_map": {
            k: {"basis": v.basis, "su": v.su, "mul": float(v.mul)}
            for k, v in UNIT_MAP.items()
        },
        "extra_units": extra_units,
        "extra_count": extra_count,
        "multi_pack": multi_pack,
        "promo_markers": _typed_markers(dict(PROMO_MARKERS)),
        "bundle_markers": _typed_markers(dict(BUNDLE_MARKERS)),
        "pack_patterns": pack_patterns,
        "unit_norm": dict(UNIT_NORM),
    }


def _swap_in_typed(extract_mod, normalize_mod, typed: dict[str, Any]) -> dict[str, Any]:
    """Replace the YAML-derived module dicts with typed-tree versions.
    Returns the saved originals so caller can restore.
    """
    saved = {
        "ex_UNIT_MAP": extract_mod._UNIT_MAP,
        "ex_EXTRA_UNITS": extract_mod._EXTRA_UNITS,
        "ex_EXTRA_COUNT": extract_mod._EXTRA_COUNT,
        "ex_MULTI_PACK": extract_mod._MULTI_PACK,
        "ex_PROMO_MARKERS": extract_mod._PROMO_MARKERS,
        "ex_BUNDLE_MARKERS": extract_mod._BUNDLE_MARKERS,
        "nm_PACK_PATTERNS": normalize_mod._PACK_PATTERNS,
        "nm_UNIT_NORM": normalize_mod._UNIT_NORM,
    }
    extract_mod._UNIT_MAP = typed["unit_map"]
    extract_mod._EXTRA_UNITS = typed["extra_units"]
    extract_mod._EXTRA_COUNT = typed["extra_count"]
    extract_mod._MULTI_PACK = typed["multi_pack"]
    extract_mod._PROMO_MARKERS = typed["promo_markers"]
    extract_mod._BUNDLE_MARKERS = typed["bundle_markers"]
    normalize_mod._PACK_PATTERNS = typed["pack_patterns"]
    normalize_mod._UNIT_NORM = typed["unit_norm"]
    return saved


def _restore(extract_mod, normalize_mod, saved: dict[str, Any]) -> None:
    extract_mod._UNIT_MAP = saved["ex_UNIT_MAP"]
    extract_mod._EXTRA_UNITS = saved["ex_EXTRA_UNITS"]
    extract_mod._EXTRA_COUNT = saved["ex_EXTRA_COUNT"]
    extract_mod._MULTI_PACK = saved["ex_MULTI_PACK"]
    extract_mod._PROMO_MARKERS = saved["ex_PROMO_MARKERS"]
    extract_mod._BUNDLE_MARKERS = saved["ex_BUNDLE_MARKERS"]
    normalize_mod._PACK_PATTERNS = saved["nm_PACK_PATTERNS"]
    normalize_mod._UNIT_NORM = saved["nm_UNIT_NORM"]


def _load_corpus(path: Path, sample: int, seed: int) -> pd.DataFrame:
    df = pd.read_parquet(path, columns=None)
    # Map known column names to the canonical (item_name, category, country, lang) shape.
    name_col = next(
        (c for c in ("product_name", "first_name", "item_name") if c in df.columns),
        None,
    )
    if name_col is None:
        sys.exit(f"corpus {path} has no recognised item-name column")
    cat_col = "category" if "category" in df.columns else None
    country_col = "country" if "country" in df.columns else None
    lang_col = "lang" if "lang" in df.columns else None

    cols = [name_col]
    if cat_col:
        cols.append(cat_col)
    if country_col:
        cols.append(country_col)
    if lang_col:
        cols.append(lang_col)
    df = df[cols].rename(
        columns={name_col: "item_name", cat_col or "_": "category"}
        if cat_col
        else {name_col: "item_name"}
    )
    df = df.dropna(subset=["item_name"])
    if sample and len(df) > sample:
        df = df.sample(n=sample, random_state=seed).reset_index(drop=True)
    if "category" not in df.columns:
        df["category"] = None
    if "country" not in df.columns:
        df["country"] = None
    if "lang" not in df.columns:
        df["lang"] = None
    return df


def _run(df: pd.DataFrame, extract_fn) -> list[Any]:
    out = []
    for r in df.itertuples():
        sf = extract_fn(
            getattr(r, "item_name"),
            getattr(r, "category", None),
            getattr(r, "country", None),
            getattr(r, "lang", None),
        )
        out.append(sf)
    return out


def _diff_row(idx: int, row: pd.Series, baseline, typed) -> list[str]:
    diffs = []
    for f in _COMPARE_FIELDS:
        bv = getattr(baseline, f)
        tv = getattr(typed, f)
        if bv != tv:
            diffs.append(
                f"row {idx}  field={f}  baseline={bv!r}  typed={tv!r}\n"
                f"  item_name={row['item_name']!r}\n"
                f"  country={row.get('country')!r}  lang={row.get('lang')!r}"
            )
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Byte-identity regression: YAML vs typed-tree extractor"
    )
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument(
        "--sample", type=int, default=5000, help="Random sample size (0 = all rows)"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-diffs", type=int, default=20)
    args = parser.parse_args(argv)

    ex = _extract_module()
    nm = _normalize_module()
    typed = _typed_dicts()

    df = _load_corpus(args.corpus, args.sample, args.seed)
    print(f"corpus={args.corpus.name} rows={len(df)} sample_seed={args.seed}")

    print("running baseline (YAML loader)...")
    baseline_out = _run(df, ex.extract)

    saved = _swap_in_typed(ex, nm, typed)
    try:
        print("running typed-tree extractor...")
        typed_out = _run(df, ex.extract)
    finally:
        _restore(ex, nm, saved)

    diff_count = 0
    diff_buf: list[str] = []
    for i, (b, t) in enumerate(zip(baseline_out, typed_out)):
        row_diffs = _diff_row(i, df.iloc[i], b, t)
        if row_diffs:
            diff_count += 1
            if len(diff_buf) < args.max_diffs:
                diff_buf.extend(row_diffs)

    if diff_count == 0:
        print(f"0 diffs across {len(df)} rows")
        return 0

    print(f"{diff_count} rows differ ({len(df)} total). First {len(diff_buf)} diffs:")
    for line in diff_buf:
        print(line)
        print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
