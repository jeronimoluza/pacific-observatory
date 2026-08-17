"""Unit tests for the gold-label audit scaffold.

All synthetic: no model fit, no embedding call, no gold read. These pin the
arithmetic and the bookkeeping — the parts that would silently produce a wrong
suspect ranking rather than an error.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.enrich.classifier.dataset import _apply_corrections
from prices.enrich.gold_audit import neighbors, oof, score, signals

pytestmark = pytest.mark.unit


def _unit_rows(vectors: list[list[float]]) -> np.ndarray:
    m = np.asarray(vectors, dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class TestNeighbors:
    def test_excludes_self_from_own_neighbours(self):
        mat = _unit_rows([[1, 0], [0.99, 0.1], [0, 1]])
        idx, sim = neighbors._topk_within(mat, k=2)
        for i, row in enumerate(idx):
            assert i not in row

    def test_neighbours_are_sorted_by_descending_similarity(self):
        mat = _unit_rows([[1, 0], [0.9, 0.4], [0.2, 1], [-1, 0]])
        _, sim = neighbors._topk_within(mat, k=3)
        for row in sim:
            assert list(row) == sorted(row, reverse=True)

    def test_k_is_clamped_to_available_neighbours(self):
        mat = _unit_rows([[1, 0], [0, 1]])
        idx, _ = neighbors._topk_within(mat, k=10)
        assert idx.shape == (2, 1)

    def test_purity_is_share_of_neighbours_sharing_the_gold_code(self):
        codes = np.array(["A", "A", "A", "B", "B"], dtype=object)
        idx = np.array([[1, 3], [0, 2], [0, 1], [4, 0], [3, 0]], dtype=np.int32)
        sim = np.full((5, 2), 0.5, dtype=np.float32)
        row_ids = np.array(["r0", "r1", "r2", "r3", "r4"])
        out = neighbors._division_frame(codes, row_ids, idx, sim)
        # row 0 (A) neighbours are A and B -> half share its own code
        assert out.loc[0, "purity_at_k"] == pytest.approx(0.5)
        # row 1 (A) neighbours are both A
        assert out.loc[1, "purity_at_k"] == pytest.approx(1.0)

    def test_flags_disagreement_when_neighbour_majority_differs(self):
        codes = np.array(["A", "B", "B", "B"], dtype=object)
        idx = np.array([[1, 2], [2, 3], [1, 3], [1, 2]], dtype=np.int32)
        sim = np.full((4, 2), 0.5, dtype=np.float32)
        out = neighbors._division_frame(
            codes, np.array(["r0", "r1", "r2", "r3"]), idx, sim
        )
        assert bool(out.loc[0, "neighbor_disagrees"]) is True
        assert bool(out.loc[1, "neighbor_disagrees"]) is False
        assert out.loc[0, "neighbor_majority_code"] == "B"


class TestOofEligibility:
    def _gold(self):
        return pd.DataFrame(
            {
                "verdict": ["leaf"] * 6 + ["exclude"],
                "code": ["01.1", "01.1", "01.2", "01.1", "01.2", "01.3", "01.1"],
            }
        )

    def test_non_leaf_verdicts_are_never_scored(self):
        status = oof._eligible(self._gold(), min_support=1)
        assert status.iloc[6] == oof.STATUS_NOT_LEAF

    def test_leaves_below_min_support_are_marked_not_dropped(self):
        status = oof._eligible(self._gold(), min_support=2)
        # 01.3 appears once among leaf rows
        assert status.iloc[5] == oof.STATUS_THIN_LEAF
        # nothing is lost: every input row still has a status
        assert len(status) == 7

    def test_min_support_counts_only_leaf_verdict_rows(self):
        # 01.1 has 3 leaf rows plus 1 excluded row; at min_support=4 the
        # excluded row must not rescue it.
        status = oof._eligible(self._gold(), min_support=4)
        assert set(status.iloc[:6]) == {oof.STATUS_THIN_LEAF}


class TestDuplicateConflict:
    def test_dupe_key_ignores_case_and_punctuation(self):
        assert signals._dupe_key("Coca-Cola 1.5L") == signals._dupe_key(
            "coca cola 1 5l"
        )

    def test_dupe_key_keeps_pack_size_distinct(self):
        # different SKUs must not collide, or the audit invents conflicts
        assert signals._dupe_key("Milk 200g") != signals._dupe_key("Milk 1kg")

    def test_flags_only_keys_carrying_more_than_one_code(self):
        gold = pd.DataFrame(
            {
                "gold_row_id": ["a", "b", "c", "d"],
                "product_name": ["Rice 1kg", "rice 1kg", "Salt 500g", "Sugar 1kg"],
                "code": ["01.1.1", "01.1.2", "01.7.1", "01.8.1"],
            }
        )
        out = signals._dupe_conflict(gold)
        assert list(out["dupe_conflict"]) == [True, True, False, False]

    def test_agreeing_duplicates_are_not_flagged(self):
        gold = pd.DataFrame(
            {
                "gold_row_id": ["a", "b"],
                "product_name": ["Rice 1kg", "RICE 1KG"],
                "code": ["01.1.1", "01.1.1"],
            }
        )
        assert not signals._dupe_conflict(gold)["dupe_conflict"].any()


class TestConfusionPairs:
    def _frame(self, n_repeats: int, conf: float):
        return pd.DataFrame(
            {
                "oof_status": [oof.STATUS_OK] * n_repeats,
                "oof_correct": [False] * n_repeats,
                "oof_conf": [conf] * n_repeats,
                "code": ["01.1.1"] * n_repeats,
                "oof_pred": ["01.1.2"] * n_repeats,
            }
        )

    def test_recurring_high_confidence_errors_become_a_pair(self):
        pairs = signals._confusion_pairs(self._frame(signals.CONFUSION_MIN_COUNT, 0.95))
        assert ("01.1.1", "01.1.2") in pairs

    def test_rare_errors_are_ignored(self):
        pairs = signals._confusion_pairs(
            self._frame(signals.CONFUSION_MIN_COUNT - 1, 0.95)
        )
        assert pairs == set()

    def test_low_confidence_errors_are_ignored(self):
        pairs = signals._confusion_pairs(self._frame(signals.CONFUSION_MIN_COUNT, 0.10))
        assert pairs == set()


class TestScoring:
    def _signals(self):
        return pd.DataFrame(
            {
                "gold_row_id": ["clean", "neighbour_only", "loud"],
                "oof_confidently_disagrees": [False, False, True],
                "oof_disagrees": [False, False, True],
                "neighbor_disagrees": [False, True, True],
                "dupe_conflict": [False, False, True],
                "confusion_pair": [False, False, True],
                "label_source": ["consensus_AB", "consensus_AB", "adjudicated_opus"],
                "confidence": ["high", "high", "low"],
                "disagreement_type": ["agree", "agree", "leaf_cross_class"],
            }
        )

    def test_unremarkable_rows_score_zero(self):
        ind = score._indicators(self._signals())
        assert not ind.iloc[0].any()

    def test_score_orders_by_accumulated_signal(self):
        df = self._signals()
        ind = score._indicators(df)
        totals = sum(ind[c].astype(float) * w for c, w in score.DEFAULT_WEIGHTS.items())
        assert totals.iloc[2] > totals.iloc[1] > totals.iloc[0]

    def test_missing_signal_columns_do_not_flag_rows(self):
        df = self._signals().drop(columns=["confidence", "disagreement_type"])
        ind = score._indicators(df)
        assert not ind["low_confidence"].any()
        assert not ind["original_disagreement"].any()

    def test_every_weight_has_a_matching_indicator(self):
        ind = score._indicators(self._signals())
        assert set(ind.columns) == set(score.DEFAULT_WEIGHTS)


class TestCorrectionsRoundTrip:
    """The audit writes corrections; `dataset._apply_corrections` reads them."""

    def _write(self, tmp_path, rows):
        cdir = tmp_path / "corrections"
        cdir.mkdir()
        pd.DataFrame(rows).to_csv(cdir / "20260817T000000Z.csv", index=False)
        return tmp_path

    def _gold(self):
        return pd.DataFrame({"gold_row_id": ["a", "b"], "code": ["01.1.1", "01.2.2"]})

    def test_review_status_does_not_change_gold(self, tmp_path):
        gold_dir = self._write(
            tmp_path,
            [{"gold_row_id": "a", "new_code": "01.9.9", "status": "review"}],
        )
        out = _apply_corrections(self._gold(), gold_dir)
        assert out.loc[0, "code"] == "01.1.1"

    def test_apply_status_overlays_the_new_code(self, tmp_path):
        gold_dir = self._write(
            tmp_path,
            [{"gold_row_id": "a", "new_code": "01.9.9", "status": "apply"}],
        )
        out = _apply_corrections(self._gold(), gold_dir)
        assert out.loc[0, "code"] == "01.9.9"
        assert out.loc[1, "code"] == "01.2.2"

    def test_absent_corrections_dir_is_a_no_op(self, tmp_path):
        out = _apply_corrections(self._gold(), tmp_path)
        assert list(out["code"]) == ["01.1.1", "01.2.2"]
