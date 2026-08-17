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
from prices.enrich.gold_audit import (
    adjudicate,
    batching,
    neighbors,
    oof,
    score,
    signals,
)

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


def _suspects(n_disputed: int = 10, n_clean: int = 8) -> pd.DataFrame:
    """Disputed rows on one pair, plus undisputed rows eligible as controls."""
    disputed = pd.DataFrame(
        {
            "gold_row_id": [f"d{i}" for i in range(n_disputed)],
            "product_name": [f"disputed {i}" for i in range(n_disputed)],
            "code": ["01.1.1"] * n_disputed,
            "oof_pred": ["01.1.2"] * n_disputed,
            "oof_correct": [False] * n_disputed,
            "purity_at_k": [0.2] * n_disputed,
            "suspicion_score": [5.0] * n_disputed,
            "neighbor_disagrees": [True] * n_disputed,
            "oof_disagrees": [True] * n_disputed,
        }
    )
    clean = pd.DataFrame(
        {
            "gold_row_id": [f"c{i}" for i in range(n_clean)],
            "product_name": [f"clean {i}" for i in range(n_clean)],
            "code": ["01.1.1", "01.1.2"] * (n_clean // 2),
            "oof_pred": ["01.1.1", "01.1.2"] * (n_clean // 2),
            "oof_correct": [True] * n_clean,
            "purity_at_k": [1.0] * n_clean,
            "suspicion_score": [0.0] * n_clean,
            "neighbor_disagrees": [False] * n_clean,
            "oof_disagrees": [False] * n_clean,
        }
    )
    return pd.concat([disputed, clean], ignore_index=True)


class TestDisputePair:
    def test_pair_is_unordered(self):
        assert batching.dispute_pair("01.2", "01.1") == batching.dispute_pair(
            "01.1", "01.2"
        )

    def test_agreement_is_not_a_dispute(self):
        assert batching.dispute_pair("01.1", "01.1") is None

    def test_missing_prediction_is_not_a_dispute(self):
        assert batching.dispute_pair("01.1", None) is None


class TestControlPool:
    def test_only_undisputed_pure_rows_qualify(self):
        pool = batching.control_pool(_suspects())
        assert set(pool["gold_row_id"]) == {f"c{i}" for i in range(8)}

    def test_impure_neighbourhood_disqualifies_a_control(self):
        df = _suspects()
        df.loc[df["gold_row_id"] == "c0", "purity_at_k"] = 0.9
        assert "c0" not in set(batching.control_pool(df)["gold_row_id"])

    def test_any_suspicion_disqualifies_a_control(self):
        df = _suspects()
        df.loc[df["gold_row_id"] == "c1", "suspicion_score"] = 0.5
        assert "c1" not in set(batching.control_pool(df)["gold_row_id"])


class TestPairBatching:
    def _plan(self, **kw):
        df = _suspects()
        picked = df[df["suspicion_score"] > 0]
        return batching.plan(picked, batching.control_pool(df), **kw)

    def test_rows_are_split_evenly_with_no_runt_batch(self):
        # 10 rows at batch_size 4 -> three near-equal batches, not 4+4+2
        plans = self._plan(batch_size=4)
        assert [b["n_real"] for b in plans] == [4, 3, 3]

    def test_no_batch_carries_more_controls_than_real_rows(self):
        for b in self._plan(batch_size=4):
            assert len(b["control_row_ids"]) <= b["n_real"]

    def test_every_batch_carries_controls(self):
        for b in self._plan(batch_size=4):
            assert len(b["control_row_ids"]) >= 1

    def test_controls_are_never_reused_across_batches(self):
        seen = [i for b in self._plan(batch_size=4) for i in b["control_row_ids"]]
        assert len(seen) == len(set(seen))

    def test_controls_share_the_batch_pair_so_they_blend_in(self):
        for b in self._plan(batch_size=4):
            expected = b["control_expected"]
            assert all(code in b["pair"] for code in expected.values())

    def test_control_ids_are_present_in_the_exported_rows(self):
        for b in self._plan(batch_size=4):
            assert set(b["control_row_ids"]) <= set(b["rows"]["gold_row_id"])

    def test_max_pairs_keeps_only_the_largest_disputes(self):
        df = _suspects()
        extra = df.iloc[:1].copy()
        extra["gold_row_id"] = ["rare"]
        extra["code"] = ["09.9.9"]
        extra["oof_pred"] = ["09.9.8"]
        picked = pd.concat([df[df["suspicion_score"] > 0], extra], ignore_index=True)
        plans = batching.plan(picked, batching.control_pool(df), max_pairs=1)
        assert {tuple(b["pair"]) for b in plans} == {("01.1.1", "01.1.2")}

    def test_planning_is_deterministic(self):
        first, second = self._plan(batch_size=4), self._plan(batch_size=4)
        assert [b["control_row_ids"] for b in first] == [
            b["control_row_ids"] for b in second
        ]


class TestBlindPayload:
    def _payload(self, seed: int = 0):
        row = pd.Series({"gold_row_id": "d0", "product_name": "X", "country": "PHL"})
        return adjudicate._payload(
            row, ["01.1.1", "01.1.2"], np.random.default_rng(seed)
        )

    def test_payload_never_names_the_current_gold_label(self):
        leaky = {
            "current_gold_code",
            "code",
            "oof_pred",
            "neighbor_majority_code",
            "suspicion_score",
            "signals",
            "why_flagged",
        }
        assert leaky.isdisjoint(self._payload())

    def test_both_candidates_are_offered(self):
        assert sorted(self._payload()["candidate_codes"]) == ["01.1.1", "01.1.2"]

    def test_candidate_order_is_not_fixed_to_gold_first(self):
        orders = {tuple(self._payload(s)["candidate_codes"]) for s in range(12)}
        assert len(orders) == 2

    def test_prompt_carries_the_definitions_and_examples_once(self):
        text = adjudicate._prompt(
            ["01.1.1", "01.1.2"], "DEFBLOCK", {"01.1.1": ["ex a"], "01.1.2": []}
        )
        assert text.count("DEFBLOCK") == 1
        assert "ex a" in text
        assert "(none available)" in text

    def test_prompt_permits_a_third_answer(self):
        text = adjudicate._prompt(["01.1.1", "01.1.2"], "D", {})
        assert "neither candidate is right" in text


class TestSubsets:
    def test_both_disagree_needs_two_independent_signals(self):
        df = pd.DataFrame(
            {
                "neighbor_disagrees": [True, True, False, None],
                "oof_disagrees": [True, False, True, True],
                "suspicion_score": [5.0, 2.0, 2.0, 2.0],
            }
        )
        assert list(score.SUBSETS["both-disagree"](df)) == [True, False, False, False]

    def test_unknown_subset_is_rejected(self, monkeypatch):
        monkeypatch.setattr(score, "load", lambda _: _suspects())
        with pytest.raises(ValueError, match="unknown subset"):
            score.top("run", 10, subset="nope")

    def test_non_positive_n_means_no_limit(self, monkeypatch):
        monkeypatch.setattr(score, "load", lambda _: _suspects())
        assert len(score.top("run", 0, subset="both-disagree")) == 10
        assert len(score.top("run", 3, subset="both-disagree")) == 3


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

    def test_invalid_status_never_reaches_gold(self, tmp_path):
        # codex sometimes answers with an intermediate node rather than a leaf;
        # ingest marks those "invalid" and they must stay inert even if a human
        # bulk-promotes a round.
        gold_dir = self._write(
            tmp_path,
            [{"gold_row_id": "a", "new_code": "01.1.8.9", "status": "invalid"}],
        )
        out = _apply_corrections(self._gold(), gold_dir)
        assert out.loc[0, "code"] == "01.1.1"
