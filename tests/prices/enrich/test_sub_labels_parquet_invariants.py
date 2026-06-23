"""Invariants for the regenerated `_sub_labels.parquet` (SUBLAB-05).

The parquet is the tier-b retrieval vocabulary, derived from
`_sub_labels_store.json` via `regenerate_sub_labels_parquet.build_df`. These
tests pin the schema, the code-depth granularity, the English-only / prose-free
invariants carried over from the store rebuild, and — crucially — the
NON-EMPTY-VOCAB-PER-LEAF guarantee that closes the anchor-id-length gate defect:
no leaf that has a sub-vocabulary in the store may be silently starved to
`_other`-only by the `_CLEAN_ANCHOR_MAX_ID_LEN` gate in `taxonomy_index`.

Reconciliation with the 538-leaf taxonomy: the store keys all 538 deepest
COICOP leaves, but 48 of them are genuine prose-only n.e.c. catch-alls left
intentionally empty (D1/D3 — no extractable grounded short item). The parquet
therefore carries exactly the 490 leaves that DO have a grounded vocabulary
(227 food 5-digit + 263 non-food 4-digit + 0 food 4-digit).
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

# Non-empty leaf counts (the 48 prose-only catch-alls are intentionally absent).
_FOOD_5DIGIT = 227
_NONFOOD_4DIGIT = 263
_TOTAL_NONEMPTY = _FOOD_5DIGIT + _NONFOOD_4DIGIT  # 490


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
