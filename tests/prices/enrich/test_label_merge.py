"""Unit tests for the gold-labeling A/B merge stage.

`classify_disagreement` is the reverse-engineered `disagreement_type` rule
(validated to 100% against the recovered gold_v5_merged.parquet); `build_merged`
joins batch metadata with the two pass outputs into the merged frame + the
non-agree disagreements worklist.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from prices.enrich import label_merge

pytestmark = [pytest.mark.unit]


def test_agree_when_verdict_and_code_match():
    va, ca, da, dt = label_merge.classify_disagreement(
        "leaf", "01.1.1.3.9", "01", "leaf", "01.1.1.3.9", "01"
    )
    assert (va, ca, da, dt) == (True, True, True, "agree")


def test_verdict_conflict_takes_priority():
    _, _, _, dt = label_merge.classify_disagreement(
        "leaf", "01.1.1.3.9", "01", "exclude", "", ""
    )
    assert dt == "verdict_conflict"


def test_leaf_within_vs_cross_class_by_group():
    # same group 01.1 -> within
    _, _, _, dt = label_merge.classify_disagreement(
        "leaf", "01.1.1.5.0", "01", "leaf", "01.1.9.1.1", "01"
    )
    assert dt == "leaf_within_class"
    # different group (01.1 vs 01.2) though same division -> cross
    _, _, _, dt = label_merge.classify_disagreement(
        "leaf", "01.1.9.3.9", "01", "leaf", "01.2.9.0.0", "01"
    )
    assert dt == "leaf_cross_class"


def test_nonleaf_buckets():
    _, _, _, dt = label_merge.classify_disagreement(
        "ambiguous_class", "0111", "01", "ambiguous_class", "0112", "01"
    )
    assert dt == "class_conflict"
    _, _, _, dt = label_merge.classify_disagreement(
        "exclude", "05", "05", "exclude", "13", "13"
    )
    assert dt == "code_conflict"


def _label(rid, verdict, code, division, basis="true", rationale="r"):
    return {
        "gold_row_id": rid,
        "verdict": verdict,
        "code": code,
        "division": division,
        "pricing_basis_plausible": basis,
        "rationale": rationale,
    }


def test_build_merged_joins_and_flags(tmp_path):
    batches = tmp_path / "batches"
    labels = tmp_path / "labels"
    batches.mkdir()
    labels.mkdir()
    pd.DataFrame(
        {
            "gold_row_id": ["gv5-00000", "gv5-00001"],
            "product_name_original": ["Milk 1L", "Cola 330ml"],
            "country": ["fiji", "fiji"],
            "source": ["shop", "shop"],
            "channel": [None, None],
            "category": [None, None],
            "declared_coicop_codes": [None, None],
            "price": [1.0, 2.0],
        }
    ).to_csv(batches / "gold_v5_batch_000.csv", index=False)
    (labels / "pass_a_batch_000.json").write_text(
        json.dumps(
            [
                _label("gv5-00000", "leaf", "01.1.4.1.1", "01"),
                _label("gv5-00001", "leaf", "01.2.1.0.0", "01"),
            ]
        )
    )
    (labels / "pass_b_batch_000.json").write_text(
        json.dumps(
            [
                _label("gv5-00000", "leaf", "01.1.4.1.1", "01"),  # agree
                _label(
                    "gv5-00001", "leaf", "01.2.9.0.0", "01"
                ),  # within-class disagree
            ]
        )
    )

    merged, disagreements = label_merge.build_merged(
        labels, batches, leaves={"01.1.4.1.1", "01.2.1.0.0", "01.2.9.0.0"}
    )

    assert len(merged) == 2
    assert set(label_merge.MERGED_COLUMNS) == set(merged.columns)
    row0 = merged.set_index("gold_row_id").loc["gv5-00000"]
    assert row0["disagreement_type"] == "agree"
    assert row0["product_name"] == "Milk 1L"
    assert bool(row0["a_code_valid"]) is True
    assert row0["batch"] == "000"
    # only the non-agree row is in the worklist
    assert list(disagreements["gold_row_id"]) == ["gv5-00001"]
    assert disagreements.iloc[0]["disagreement_type"] == "leaf_within_class"
