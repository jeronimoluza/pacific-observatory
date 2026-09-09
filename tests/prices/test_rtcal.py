"""RT-CAL v1 unit tests.

These pin the decisions that are easy to break silently: which rows may train,
which direction time is allowed to flow, and what an absent signal means to the
gate. The replication-scale checks live in `test_rtcal_replication.py`, which
needs the real cell matrix and skips without it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.rtcal import folds, frames, gate, predict, targets


# ---- training eligibility -------------------------------------------------

def test_observed_cells_uses_n_trusted_not_cell_status():
    """`cell_status == "usable"` means n_trusted >= 5 and would drop most of the
    training set. The method was validated on n_trusted > 0."""
    cells = pd.DataFrame(
        {
            "period": ["2026-01"] * 4,
            "country": ["fiji"] * 4,
            "coicop_code": ["01.1.1.1.1"] * 4,
            "standard_unit": ["kg"] * 4,
            "median_unit_value_usd": [2.0, 3.0, None, 4.0],
            "n_trusted": [1, 9, 7, 0],
            "cell_status": ["thin", "usable", "usable", "thin"],
        }
    )
    out = frames.observed_cells(cells)
    assert len(out) == 2  # the n_trusted=1 thin cell trains; the null and the 0 do not
    assert set(out["n_trusted"]) == {1, 9}


def test_observed_cells_drops_nonpositive_prices():
    cells = pd.DataFrame(
        {
            "period": ["2026-01"] * 2,
            "country": ["fiji"] * 2,
            "coicop_code": ["01.1.1.1.1"] * 2,
            "standard_unit": ["kg"] * 2,
            "median_unit_value_usd": [0.0, -1.0],
            "n_trusted": [5, 5],
            "cell_status": ["usable", "usable"],
        }
    )
    assert frames.observed_cells(cells).empty


def test_contract_rejects_non_monthly_period():
    cells = pd.DataFrame(
        {
            "period": ["2026-01-15"],
            "country": ["fiji"],
            "coicop_code": ["01.1.1.1.1"],
            "standard_unit": ["kg"],
            "median_unit_value_usd": [2.0],
            "n_trusted": [3],
            "cell_status": ["thin"],
        }
    )
    with pytest.raises(frames.ContractError):
        frames.validate_contract(cells)


def test_period_index_is_one_based():
    """low_rank_svd indexes a dense matrix with period_index - 1 and sizes it
    from the max, so a 0-based index shifts every prediction by a month."""
    mapping = frames.period_index_map(["2026-03", "2026-01", "2026-02"])
    assert mapping == {"2026-01": 1, "2026-02": 2, "2026-03": 3}


# ---- time may not flow backwards -----------------------------------------

def _series_frame(period_indices, values):
    return pd.DataFrame(
        {
            "series_id": ["s"] * len(period_indices),
            "period_index": period_indices,
            "y": values,
        }
    )


def test_temporal_past_only_never_sees_the_future():
    train = _series_frame([1, 5], [1.0, 5.0])
    val = _series_frame([3, 3], [np.nan, np.nan])
    past = predict.temporal_interpolate(train, val, past_only=True)
    both = predict.temporal_interpolate(train, val, past_only=False)
    assert np.allclose(past, 1.0)  # carries the prior observation forward
    assert np.allclose(both, 3.0)  # interpolates between 1 and 5
    assert not np.allclose(past, both)


def test_temporal_past_only_returns_nan_with_no_history():
    train = _series_frame([5], [5.0])
    val = _series_frame([2], [np.nan])
    assert np.isnan(predict.temporal_interpolate(train, val, past_only=True)).all()


def test_time_forward_fold_trains_strictly_before_the_block():
    df = pd.DataFrame({"period_index": [1, 2, 3, 4], "fold_time_block": [1, 1, 2, 2]})
    train_mask, val_mask, past_only = folds.split_masks(df, "fold_time_block", 2)
    assert past_only is True
    assert df.loc[train_mask, "period_index"].max() < df.loc[val_mask, "period_index"].min()


def test_time_forward_first_block_has_no_training_data():
    df = pd.DataFrame({"period_index": [1, 2, 3, 4], "fold_time_block": [1, 1, 2, 2]})
    assert folds.split_masks(df, "fold_time_block", 1) is None


# ---- the gate -------------------------------------------------------------

def test_within_tolerance_is_symmetric_in_ratio():
    y_true = np.log(np.array([100.0, 100.0, 100.0]))
    y_pred = np.log(np.array([125.0, 80.0, 130.0]))
    assert list(gate.within_tolerance(y_true, y_pred)) == [1, 1, 0]


def test_threshold_for_precision_takes_the_loosest_qualifying_cut():
    """Taking the FIRST qualifying point would release almost nothing; the rule
    is the most coverage still compatible with the target."""
    # Top 1500 of 2000 correct. Precision is 1.00 at n=1500 and 0.75 at n=2000,
    # crossing 0.80 at n=1875 -- so a correct implementation lands there, not at
    # the first qualifying point (n=100) and not at everything (n=2000).
    scores = np.linspace(1.0, 0.0, 2000)
    labels = (np.arange(2000) < 1500).astype(int)
    threshold, n, precision = gate.threshold_for_precision(scores, labels, target=0.80, min_n=100)
    assert n == pytest.approx(1875, abs=2)
    assert precision >= 0.80
    assert threshold == pytest.approx(scores[n - 1], abs=1e-9)


def test_threshold_for_precision_releases_nothing_when_unreachable():
    scores = np.linspace(1.0, 0.0, 1000)
    labels = np.zeros(1000, dtype=int)
    threshold, n, _ = gate.threshold_for_precision(scores, labels, target=0.80, min_n=100)
    assert threshold == np.inf and n == 0


def test_gate_frame_treats_absent_dispersion_as_ignorance():
    """Missing disagreement must read as 999, not 0. Zero says 'the models
    agreed', which is exactly the wrong thing to tell the gate."""
    from prices.rtcal.features import gate_feature_frame

    df = pd.DataFrame(
        {
            **{col: [1] for col in ("series_train_count", "country_product_train_count",
                                    "product_unit_train_count", "product_period_train_count",
                                    "country_period_train_count", "period_train_count",
                                    "country_train_count", "coicop_train_count")},
            "nearest_series_gap": [np.inf],
            "period_index": [3.0],
            "candidate_model_sd": [np.nan],
            "candidate_model_range": [np.nan],
            "ensemble_structural_sd": [np.nan],
            "ensemble_structural_range": [np.nan],
            "absdiff_ridge_onehot": [np.nan],
        }
    )
    x = gate_feature_frame(df)
    assert x["candidate_model_sd"].iloc[0] == 999.0
    assert x["ensemble_structural_sd"].iloc[0] == 999.0
    assert x["absdiff_ridge_onehot"].iloc[0] == 999.0
    assert x["nearest_series_gap_capped"].iloc[0] == 999.0


# ---- missingness classification ------------------------------------------

def _classify(series_counts, last_index, target_index, country_n, product_n):
    observed = pd.DataFrame(
        {
            "series_id": ["s"] * series_counts if series_counts else [],
            "period_index": [last_index] * series_counts if series_counts else [],
            "country_period_id": ["c|p"] * series_counts if series_counts else [],
            "product_unit_period_id": ["pu|p"] * series_counts if series_counts else [],
        }
    )
    tgt = pd.DataFrame(
        {
            "series_id": ["s"],
            "period_index": [target_index],
            "country_period_id": ["c|p" if country_n else "c|other"],
            "product_unit_period_id": ["pu|p" if product_n else "pu|other"],
        }
    )
    # Force the support counts the test wants.
    observed = pd.concat([observed] * 1, ignore_index=True)
    return observed, tgt


def test_new_series_outranks_every_other_label():
    observed = pd.DataFrame(
        {"series_id": [], "period_index": [], "country_period_id": [], "product_unit_period_id": []}
    )
    tgt = pd.DataFrame(
        {"series_id": ["s"], "period_index": [5], "country_period_id": ["c"], "product_unit_period_id": ["p"]}
    )
    out = targets.classify_missingness(tgt, observed)
    assert out.iloc[0] == "new_country_product_unit_series"


def test_forward_gap_outranks_thin_support():
    observed = pd.DataFrame(
        {
            "series_id": ["s"] * 3,
            "period_index": [1, 2, 3],
            "country_period_id": ["c|1", "c|2", "c|3"],
            "product_unit_period_id": ["p|1", "p|2", "p|3"],
        }
    )
    tgt = pd.DataFrame(
        {"series_id": ["s"], "period_index": [9], "country_period_id": ["c|9"], "product_unit_period_id": ["p|9"]}
    )
    assert targets.classify_missingness(tgt, observed).iloc[0] == "future_or_latest_month_gap"


def test_interior_gap_with_balanced_support_is_mixed():
    observed = pd.DataFrame(
        {
            "series_id": ["s"] * 40,
            "period_index": [1] * 20 + [9] * 20,
            "country_period_id": ["c|5"] * 40,
            "product_unit_period_id": ["p|5"] * 40,
        }
    )
    tgt = pd.DataFrame(
        {"series_id": ["s"], "period_index": [5], "country_period_id": ["c|5"], "product_unit_period_id": ["p|5"]}
    )
    assert targets.classify_missingness(tgt, observed).iloc[0] == "normal_gap_mixed"


def test_thinness_stratum_bins():
    out = targets.thinness_stratum([0, 1, 2, 3, 5, 6, 11, 12, 400])
    assert list(out) == ["0", "1-2", "1-2", "3-5", "3-5", "6-11", "6-11", "12+", "12+"]


# ---- target universe ------------------------------------------------------

def _cells(rows):
    return pd.DataFrame(rows, columns=["period", "country", "coicop_code", "standard_unit", "period_index"])


def test_build_targets_spans_gaps_and_extends_forward():
    cells = _cells(
        [
            ("2026-01", "fiji", "01.1.1.1.1", "kg", 1),
            ("2026-02", "fiji", "01.1.1.1.1", "kg", 2),
            ("2026-03", "fiji", "01.1.1.1.1", "kg", 3),
            ("2026-04", "fiji", "01.1.1.1.1", "kg", 4),
        ]
    )
    observed = frames.add_core_ids(
        _cells(
            [
                ("2026-01", "fiji", "01.1.1.1.1", "kg", 1),
                ("2026-03", "fiji", "01.1.1.1.1", "kg", 3),
            ]
        )
    )
    out = targets.build_targets(cells, observed)
    got = set(out["period"])
    assert "2026-02" in got, "interior gap must be targeted"
    assert "2026-04" in got, "forward gap must be targeted"
    assert "2026-01" not in got and "2026-03" not in got, "observed cells are never targets"


def test_build_targets_never_returns_an_observed_cell():
    cells = _cells([("2026-01", "fiji", "01.1.1.1.1", "kg", 1)])
    observed = frames.add_core_ids(cells.copy())
    assert targets.build_targets(cells, observed).empty
