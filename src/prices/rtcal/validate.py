"""Cross-validated threshold estimation -- the pass that decides what may ship.

Runs each (fold family x fold) unit, collects out-of-fold gate scores, then
solves for the score cut that historically delivered the target precision. Those
cuts become `selected_release_thresholds.csv`, which the production run applies.

This must re-run on every refresh. New labels change the cell matrix, and a
threshold solved against a different matrix is a threshold for a different
model -- see the caveat in JERO_HANDOFF.md.

This runs sequentially, by choice. The 30 units ARE independent -- `run_unit`
reads the frame and returns a new one, touching nothing global -- so a process
pool would be correct. It was measured at ~18s per unit, ~9 minutes for the full
sweep, and buying six of those minutes is not worth adding a failure mode to the
step that decides what gets published. Should the sweep ever grow, fold-level is
the axis to parallelize; splitting the frame is NOT, because every predictor
pools across all countries by design and a shard fits a different model.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import config, folds as folds_mod, gate as gate_mod
from .features import build_gate_frame, nearest_gap_features, support_features
from .predict import compute_components

def run_unit(frame: pd.DataFrame, scheme: str, fold: int) -> pd.DataFrame | None:
    """One fold of one family. Pure: reads the frame, returns scored rows."""
    split = folds_mod.split_masks(frame, scheme, fold)
    if split is None:
        return None
    train_mask, val_mask, past_only = split

    preds, stats = compute_components(frame, train_mask, val_mask, past_only=past_only)
    train, val = frame.loc[train_mask], frame.loc[val_mask]

    support = support_features(train, val)
    support["nearest_series_gap"] = nearest_gap_features(train, val)

    candidate = folds_mod.SCHEME_CANDIDATE[scheme]
    out = build_gate_frame(val, preds, stats, candidate, support)
    out["scheme"] = folds_mod.SCHEME_LABELS[scheme]
    out["scheme_col"] = scheme
    out["fold"] = int(fold)
    out["candidate_method"] = candidate
    out["y_true"] = val["y"].to_numpy(dtype=float)
    out["y_pred"] = preds[candidate]
    out["within_25pct"] = gate_mod.within_tolerance(out["y_true"], out["y_pred"])
    out["n_trusted"] = val["n_trusted"].to_numpy(dtype=float)
    out["country"] = val["country"].to_numpy()
    out["series_id"] = val["series_id"].to_numpy()
    return out.reset_index(drop=True)


def run_all_units(df, schemes=None, k=None, verbose=True):
    """Run every (scheme, fold) unit in order.

    A unit that raises is reported and skipped rather than killing the sweep --
    losing one fold degrades a threshold estimate, losing the run wastes all 30.
    """
    schemes = list(schemes or config.FOLD_SCHEMES)
    k = k or config.K_FOLDS
    started = time.time()
    frames, errors = [], []

    for scheme in schemes:
        for fold in range(1, k + 1):
            tic = time.time()
            try:
                got = run_unit(df, scheme, fold)
            except Exception as exc:
                errors.append(f"{scheme}/{fold}: {type(exc).__name__}: {exc}")
                print(f"  UNIT FAILED {errors[-1]}", flush=True)
                continue
            if got is None:
                continue
            frames.append(got)
            if verbose:
                print(
                    f"  {folds_mod.SCHEME_LABELS[scheme]:22} fold {fold}  "
                    f"{len(got):>7,} val  {time.time()-tic:5.1f}s",
                    flush=True,
                )

    if not frames:
        raise RuntimeError("no validation units produced output")
    out = pd.concat(frames, ignore_index=True)
    if verbose:
        print(
            f"  {len(frames)} units, {len(out):,} scored rows, "
            f"{time.time()-started:.0f}s total, {len(errors)} failed",
            flush=True,
        )
    return out


def crossfit_gate(scored: pd.DataFrame) -> pd.DataFrame:
    """Score every row with a gate that never saw it.

    Per fold family: train on the other folds, predict this one. Anything else
    leaks, and a leaked gate score produces a threshold that cannot be met in
    production.
    """
    out = scored.copy()
    out["gate_score_raw"] = np.nan
    out["prob_within_25pct_calibrated"] = np.nan

    for scheme, block in out.groupby("scheme", sort=False):
        idx = block.index
        for fold in sorted(block["fold"].unique()):
            test = idx[block["fold"] == fold]
            train = idx[block["fold"] != fold]
            model = gate_mod.fit_gate(out.loc[train], out.loc[train, "within_25pct"])
            if model is None:
                continue
            out.loc[test, "gate_score_raw"] = gate_mod.score_gate(model, out.loc[test])
        # Calibrate on the pooled out-of-fold scores: every score in this block
        # was produced by a gate blind to its own row, so the calibration is
        # honest even though it is fitted once.
        calibrator = gate_mod.fit_calibrator(
            out.loc[idx, "gate_score_raw"], out.loc[idx, "within_25pct"]
        )
        out.loc[idx, "prob_within_25pct_calibrated"] = gate_mod.apply_calibrator(
            calibrator, out.loc[idx, "gate_score_raw"]
        )
    return out


RELEASE_ROLES = (
    # (role, scheme label, target, production_action)
    ("normal_gap_default", "country_month_holdout", config.NORMAL_GAP_TARGET, "release"),
    ("normal_gap_default", "product_month_holdout", config.NORMAL_GAP_TARGET, "release"),
    ("normal_gap_strict", "country_month_holdout", config.NORMAL_GAP_STRICT_TARGET, "release_when_high_stakes"),
    ("normal_gap_strict", "product_month_holdout", config.NORMAL_GAP_STRICT_TARGET, "release_when_high_stakes"),
    ("forward_time_default", "time_forward_block", config.FORWARD_TIME_TARGET, "release_as_lower_confidence"),
    ("new_series_diagnostic", "series_holdout", None, "do_not_release; route_to_labeling_or_review"),
)

SCHEME_MISSINGNESS = {
    "country_month_holdout": "country_month_gap",
    "product_month_holdout": "product_month_gap",
    "time_forward_block": "future_or_latest_month_gap",
    "series_holdout": "new_country_product_unit_series",
    "country_holdout": "cold_country",
    "product_unit_holdout": "cold_product_unit",
}


def estimate_thresholds(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for role, scheme, target, action in RELEASE_ROLES:
        block = scored[scored["scheme"] == scheme]
        if block.empty:
            continue
        scores = block["gate_score_raw"].to_numpy(dtype=float)
        labels = block["within_25pct"].to_numpy(dtype=int)
        if target is None:
            # No precision target is attainable here; report the top quartile as
            # a diagnostic so the review queue can still be ranked.
            finite = scores[np.isfinite(scores)]
            threshold = float(np.quantile(finite, 0.75)) if len(finite) else np.inf
            released = scores >= threshold
        else:
            threshold, _, _ = gate_mod.threshold_for_precision(scores, labels, target)
            released = np.isfinite(scores) & (scores >= threshold)

        metrics = gate_mod.accuracy_metrics(
            block.loc[released, "y_true"], block.loc[released, "y_pred"]
        )
        rows.append(
            {
                "implementation_role": role,
                "missingness_type": SCHEME_MISSINGNESS[scheme],
                "validation_scheme": scheme,
                "candidate_method": block["candidate_method"].iloc[0],
                "gate_score": "hgb_raw",
                "release_rule": f"cv_precision_target_{int(target*100)}pct" if target else "rank_top_25pct",
                "target_correct_within_25pct": target,
                "production_action": action,
                "gate_threshold": threshold,
                "validated_coverage": float(released.mean()),
                "validated_within_10pct": metrics["within_10pct"],
                "validated_within_25pct": metrics["within_25pct"],
                "validated_outside_25pct": 1.0 - metrics["within_25pct"],
                "validated_within_50pct": metrics["within_50pct"],
                "validated_mae_log": metrics["mae_log"],
                "validated_mape_pct": metrics["mape_pct"],
                "validated_n_eval": int(released.sum()),
                # Measured on the RAW out-of-fold score, not on the isotonic
                # output. The calibrator is fitted on these same rows, so its
                # in-sample ECE is ~0 by construction -- reporting that would
                # make the 2pp drift check unfailable, which is worse than not
                # having it. Will's comparable hgb_raw figure is 0.8%.
                "gate_calibration_error": gate_mod.calibration_error(
                    block["within_25pct"], block["gate_score_raw"]
                ),
                "isotonic_calibration_error_insample": gate_mod.calibration_error(
                    block["within_25pct"], block["prob_within_25pct_calibrated"]
                ),
                "base_correct_rate": float(block["within_25pct"].mean()),
                "n_candidates": int(len(block)),
            }
        )
    return pd.DataFrame(rows)


def thinness_report(scored: pd.DataFrame) -> pd.DataFrame:
    """Performance by how much same-series history the cell had.

    With a median series length of 3, this is the most informative cut in the
    run report -- an aggregate that pools 0-history cells with 12+ hides the
    only thing worth knowing.
    """
    rows = []
    for scheme, block in scored.groupby("scheme", sort=False):
        counts = block["series_train_count"].to_numpy(dtype=float)
        for lo, hi in config.THINNESS_BINS:
            mask = (counts >= lo) & (counts <= hi)
            if not mask.any():
                continue
            metrics = gate_mod.accuracy_metrics(block.loc[mask, "y_true"], block.loc[mask, "y_pred"])
            rows.append(
                {
                    "scheme": scheme,
                    "series_train_count": f"{lo}" if lo == hi else (f"{lo}+" if hi > 10**8 else f"{lo}-{hi}"),
                    "n": int(mask.sum()),
                    "within_25pct": metrics["within_25pct"],
                    "mae_log": metrics["mae_log"],
                }
            )
    return pd.DataFrame(rows)


def fit_production_gates(scored: pd.DataFrame) -> dict:
    """One gate per fold family, trained on ALL of that family's rows.

    The cross-fitted scores chose the thresholds; this refits on the full
    validation history for scoring real targets, which is the split
    ALGORITHM.md step 8 asks for -- train on everything, threshold on
    out-of-fold only. Keyed by scheme rather than pooled, because each scheme
    solved its own threshold and a gate trained on the union would not be
    calibrated to any of them.
    """
    artifacts = {}
    for scheme, block in scored.groupby("scheme", sort=False):
        model = gate_mod.fit_gate(block, block["within_25pct"])
        if model is None:
            continue
        raw = gate_mod.score_gate(model, block)
        # Calibrate on out-of-fold scores, never on this in-sample `raw`:
        # in-sample scores are over-separated and would flatten the isotonic
        # map into overconfidence.
        calibrator = gate_mod.fit_calibrator(block["gate_score_raw"], block["within_25pct"])
        artifacts[scheme] = {"model": model, "calibrator": calibrator}
    return artifacts


def run_validation(df, schemes=None, verbose=True):
    scored = run_all_units(df, schemes=schemes, verbose=verbose)
    if verbose:
        print("  cross-fitting gate...", flush=True)
    scored = crossfit_gate(scored)
    return scored, estimate_thresholds(scored), thinness_report(scored)
