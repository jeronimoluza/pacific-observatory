"""Invariants for the regenerated `_sub_labels.parquet` (SUBLAB-05).

The parquet is the tier-b retrieval vocabulary, derived from
`_sub_labels_store.json` via `regenerate_sub_labels_parquet.build_df`. These
tests pin the schema, the code-depth granularity, the English-only / prose-free
invariants carried over from the store rebuild, and — crucially — the
NON-EMPTY-VOCAB-PER-LEAF guarantee that closes the anchor-id-length gate defect:
no leaf that has a sub-vocabulary in the store may be silently starved to
`_other`-only by the `_CLEAN_ANCHOR_MAX_ID_LEN` gate in `taxonomy_index`.

Reconciliation with the 538-leaf taxonomy: the store keys all 538 deepest
COICOP leaves, and after the Phase 0.9 atomization pass every one of them
carries a grounded vocabulary (the 48 formerly-empty prose-only catch-alls
were filled by thin-leaf enrichment). The parquet therefore carries all 538
leaves (269 food 5-digit + 269 non-food 4-digit + 0 food 4-digit).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from prices.enrich.tier_b import taxonomy_index

_PARQUET = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "prices"
    / "enrich"
    / "keywords"
    / "coicop"
    / "_sub_labels.parquet"
)

# Post-atomization leaf counts: all 538 leaves now carry a grounded vocabulary
# (the 48 formerly-empty prose-only catch-alls were filled in Phase 0.9).
_FOOD_5DIGIT = 269
_NONFOOD_4DIGIT = 269
_TOTAL_NONEMPTY = _FOOD_5DIGIT + _NONFOOD_4DIGIT  # 538

# Aggregate row-count ceiling (Pitfall 3 — class-6/7 cross-product growth guard).
# Current parquet: 2556 rows INCLUDING 426 case-dup rows → ~2130 rows post-dedup.
# Atomization removes the case dups but class-6/7 cross-products
# (e.g. "salted, dried or smoked meat of: × N animals") plus 48-leaf thin
# enrichment grow the count. The bound is 2 × 2130 = 4260 (2× the post-dedup
# baseline): generous enough to admit legitimate cross-product expansion, tight
# enough that a runaway class-6/7 balloon trips it.
_MAX_PARQUET_ROWS = 4260


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    if not _PARQUET.exists():
        pytest.skip(f"parquet absent at {_PARQUET}")
    return pd.read_parquet(_PARQUET)


@pytest.mark.integration
def test_schema_unchanged(df):
    assert list(df.columns) == ["coicop_code", "id", "label", "lang", "role"]


@pytest.mark.integration
def test_code_depth_split(df):
    codes = df["coicop_code"].astype(str).unique()
    assert (
        len(codes) == _TOTAL_NONEMPTY
    ), f"expected {_TOTAL_NONEMPTY} codes, got {len(codes)}"
    food5 = [c for c in codes if c.startswith("01") and c.count(".") == 4]
    nonfood4 = [c for c in codes if (not c.startswith("01")) and c.count(".") == 3]
    food4 = [c for c in codes if c.startswith("01") and c.count(".") == 3]
    assert len(food5) == _FOOD_5DIGIT, f"food 5-digit: {len(food5)}"
    assert len(nonfood4) == _NONFOOD_4DIGIT, f"non-food 4-digit: {len(nonfood4)}"
    assert len(food4) == 0, f"food 4-digit codes must be 0, got {len(food4)}"


@pytest.mark.integration
def test_english_only(df):
    langs = set(df["lang"].astype(str).unique())
    assert langs == {"en"}, f"lang must be en-only, got {langs}"


@pytest.mark.integration
def test_no_prose_labels(df):
    low = df["label"].astype(str).str.lower()
    bad = df[
        low.str.contains("n.e.c", regex=False)
        | low.str.startswith("other ")
        | low.str.contains("including", regex=False)
    ]
    assert bad.empty, f"prose labels present: {bad['label'].tolist()[:10]}"


@pytest.mark.integration
def test_all_anchor_role(df):
    roles = set(df["role"].astype(str).unique())
    assert roles == {"anchor"}, f"every role must be 'anchor', got {roles}"


@pytest.mark.integration
def test_non_empty_vocab_per_leaf(df):
    """Closes the anchor-id-gate defect: every leaf present in the parquet must
    survive `load_taxonomy_index()` with a non-empty sub-vocabulary beyond
    `_other`. Guards that `_CLEAN_ANCHOR_MAX_ID_LEN` is high enough to admit
    every grounded anchor, however long its slug."""
    taxonomy_index._TAXONOMY_INDEX = None
    leaves, sub_index = taxonomy_index.load_taxonomy_index()
    parquet_codes = set(df["coicop_code"].astype(str).unique())
    starved = [
        c for c in parquet_codes if len(sub_index.get(c, {"_other"}) - {"_other"}) < 1
    ]
    assert (
        not starved
    ), f"{len(starved)} leaves starved to _other-only: {sorted(starved)[:10]}"


@pytest.mark.integration
def test_parquet_case_deduped(df):
    """SC-4a (parquet projection): no two rows sharing a (coicop_code, id) have
    labels equal after .lower(). Catches the 426 case-variant dup rows if the
    merge ever re-introduces a [label, label.lower()] keyword list."""
    low = df["label"].astype(str).str.lower()
    grouped = df.assign(_label_low=low).groupby(["coicop_code", "id"])
    dup_groups = grouped["_label_low"].apply(lambda s: s.duplicated().any())
    offenders = dup_groups[dup_groups].index.tolist()
    assert not offenders, (
        f"{len(offenders)} (coicop_code, id) groups carry case-variant dup "
        f"labels (expected 0): {offenders[:10]}"
    )


@pytest.mark.integration
def test_parquet_row_ceiling(df):
    """Pitfall 3 — aggregate growth guard. Bounds the TOTAL parquet row count
    so a class-6/7 cross-product balloon trips a hard backstop. Complements
    (does not replace) Plan 02's per-leaf ~40 cap: per-leaf bounds a single-leaf
    balloon, this bounds the aggregate. No silent truncation anywhere."""
    assert len(df) <= _MAX_PARQUET_ROWS, (
        f"parquet has {len(df)} rows, exceeds ceiling {_MAX_PARQUET_ROWS} "
        "(class-6/7 cross-product balloon?)"
    )
