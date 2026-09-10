"""The production pass: fit once, score every target, release almost none of it.

Sequence follows FULL_DATASET_RUNBOOK.md -- load, validate, derive, prune,
classify missingness, fit, predict, gate, calibrate, threshold, write.

Targets are scored in two passes rather than one, because the temporal residual
has to obey a different rule on each. A forward gap must not interpolate across
its own future, so it gets `past_only=True`; an interior gap is allowed to see
both sides. Running one pass with a single flag would either cripple interior
gaps or leak the future into forward ones.

Nothing here overwrites an observed value. Fills live in their own tables.
"""

from __future__ import annotations

import json
import pickle
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import (
    config,
    frames,
    gate as gate_mod,
    prune as prune_mod,
    targets as targets_mod,
)
from .features import build_gate_frame, nearest_gap_features, support_features
from .predict import compute_components

# missingness_type -> (validation scheme whose gate scores it, release role)
GATE_FOR_MISSINGNESS = {
    "country_month_gap": ("country_month_holdout", "normal_gap_default"),
    "product_month_gap": ("product_month_holdout", "normal_gap_default"),
    # A mixed gap is judged on the country-month rule, the stricter of the two.
    "normal_gap_mixed": ("country_month_holdout", "normal_gap_default"),
    "future_or_latest_month_gap": ("time_forward_block", "forward_time_default"),
    "new_country_product_unit_series": ("series_holdout", "new_series_diagnostic"),
}

FORWARD_TYPES = ("future_or_latest_month_gap",)

OUTPUT_COLS = [
    "run_id",
    "method_id",
    "model_version",
    "period",
    "period_index",
    "country",
    "coicop_code",
    "standard_unit",
    "product_unit_id",
    "country_product_id",
    "series_id",
    "missingness_type",
    "thinness_stratum",
    "selected_predictor",
    "predicted_log_median_unit_value_usd",
    "predicted_median_unit_value_usd",
    "gate_model",
    "gate_score_raw",
    "prob_within_25pct_calibrated",
    "release_rule",
    "release_threshold",
    "release_status",
    "target_correct_within_25pct",
    "series_train_count",
    "country_product_train_count",
    "product_unit_train_count",
    "product_period_train_count",
    "country_period_train_count",
    "period_train_count",
    "country_train_count",
    "coicop_train_count",
    "nearest_series_gap",
    "component_prediction_count",
    "component_prediction_sd",
    "component_prediction_range",
    "pruning_version",
    "label_batch_version",
    "created_at",
]


def _write_pruned_cells(flagged: pd.DataFrame) -> None:
    """Publish the rejected cells so the dashboards can drop them too.

    Pruning is not only a training filter. The point of it, in Will's words, is
    that the historical view is full of values that are "obviously wrong" and
    should stop being drawn -- so the same judgement that keeps a cell out of the
    fit has to be readable by whatever draws the chart. Keyed exactly like the
    summary parquet so a consumer can anti-join without deriving anything.
    """
    cols = ["country", "coicop_code", "standard_unit", "period"]
    out = flagged[
        cols + ["median_unit_value_usd", "n_trusted", "outlier_reason"]
    ].copy()
    config.PRUNED_CELLS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(config.PRUNED_CELLS_PARQUET, index=False)


def load_thresholds(path=None) -> pd.DataFrame:
    """Promoted policy if one exists, otherwise the packaged seed."""
    if path is None:
        path = config.RELEASE_THRESHOLDS_CSV
        if not path.exists():
            path = config.RELEASE_THRESHOLDS_SEED
    table = pd.read_csv(path)
    table["gate_threshold"] = pd.to_numeric(table["gate_threshold"], errors="coerce")
    return table


def _threshold_for(table, role, missingness):
    hit = table[
        (table["implementation_role"] == role)
        & (table["missingness_type"] == missingness)
    ]
    if hit.empty and role == "normal_gap_default":
        hit = table[table["missingness_type"] == "country_month_gap"]
    if hit.empty:
        return np.inf, None, None
    row = hit.iloc[0]
    return (
        float(row["gate_threshold"]),
        row.get("release_rule"),
        row.get("target_correct_within_25pct"),
    )


def _score_pass(df, train_mask, target_mask, past_only, candidate):
    preds, stats = compute_components(df, train_mask, target_mask, past_only=past_only)
    train, val = df.loc[train_mask], df.loc[target_mask]
    support = support_features(train, val)
    support["nearest_series_gap"] = nearest_gap_features(train, val)
    frame = build_gate_frame(val, preds, stats, candidate, support)
    frame["component_prediction_sd"] = stats["ensemble_context_sd"]
    frame["component_prediction_range"] = stats["ensemble_context_range"]
    frame["component_prediction_count"] = stats["ensemble_context_n"]
    frame["selected_predictor"] = candidate
    frame["prediction"] = preds[candidate]
    return frame


def run(
    summary_path=None,
    artifacts_dir=None,
    thresholds_path=None,
    label_batch_version="unknown",
    verbose=True,
):
    started = time.time()
    run_id = f"rtcal_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    artifacts_dir = artifacts_dir or config.MODEL_ARTIFACTS_DIR

    if verbose:
        print("== load and prune ==", flush=True)
    cells = frames.load_cells(summary_path)
    observed = frames.observed_cells(cells)
    context = frames.load_country_context()
    observed, unmatched = frames.attach_country_context(observed, context)
    observed = frames.add_derived_features(observed)
    train_frame, flagged, pruning_summary = prune_mod.prune(observed)
    _write_pruned_cells(flagged)
    if verbose:
        print(
            f"  observed {pruning_summary['input_rows']:,} -> train {pruning_summary['pruned_rows']:,}",
            flush=True,
        )

    if verbose:
        print("== targets ==", flush=True)
    target_frame, _ = targets_mod.prepare_targets(cells, train_frame, context)
    if verbose:
        counts = target_frame["missingness_type"].value_counts()
        for name, n in counts.items():
            print(f"  {name:34} {n:>9,}", flush=True)

    combined = pd.concat([train_frame, target_frame], ignore_index=True, sort=False)
    is_train = np.zeros(len(combined), dtype=bool)
    is_train[: len(train_frame)] = True
    missingness = combined["missingness_type"].to_numpy()

    scored_parts = []
    for label, forward in (("interior", False), ("forward", True)):
        wanted = (
            np.isin(missingness, FORWARD_TYPES)
            if forward
            else (~is_train & ~np.isin(missingness, FORWARD_TYPES))
        )
        target_mask = wanted & ~is_train
        if not target_mask.any():
            continue
        # Normal gaps ride the relative-temporal predictor; forward and
        # cold-start gaps ride the context ensemble, per the package defaults.
        candidate = "ensemble_context" if forward else "relative_decomp_temporal"
        if verbose:
            print(f"== score {label}: {target_mask.sum():,} targets ==", flush=True)
        part = _score_pass(
            combined, is_train, target_mask, past_only=forward, candidate=candidate
        )
        for col in (
            "period",
            "period_index",
            "country",
            "coicop_code",
            "standard_unit",
            "product_unit_id",
            "country_product_id",
            "series_id",
            "missingness_type",
        ):
            part[col] = combined.loc[target_mask, col].to_numpy()
        # A cold-start cell is scored by the series-holdout gate whatever pass
        # it rode in on -- the predictor and the gate are chosen separately.
        part.loc[
            part["missingness_type"] == "new_country_product_unit_series",
            "selected_predictor",
        ] = "ensemble_context"
        scored_parts.append(part)

    scored = pd.concat(scored_parts, ignore_index=True)

    if verbose:
        print("== gate ==", flush=True)
    with open(artifacts_dir / "gates.pkl", "rb") as fh:
        gates = pickle.load(fh)
    thresholds = load_thresholds(thresholds_path)

    scored["gate_score_raw"] = np.nan
    scored["prob_within_25pct_calibrated"] = np.nan
    scored["release_threshold"] = np.inf
    scored["release_rule"] = None
    scored["target_correct_within_25pct"] = np.nan
    scored["gate_model"] = None

    for missing_type, block in scored.groupby("missingness_type", sort=False):
        scheme, role = GATE_FOR_MISSINGNESS.get(
            missing_type, ("country_month_holdout", "normal_gap_default")
        )
        artifact = gates.get(scheme)
        idx = block.index
        scored.loc[idx, "gate_model"] = f"hgb_raw::{scheme}"
        if artifact is None:
            continue
        raw = gate_mod.score_gate(artifact["model"], block)
        scored.loc[idx, "gate_score_raw"] = raw
        scored.loc[idx, "prob_within_25pct_calibrated"] = gate_mod.apply_calibrator(
            artifact["calibrator"], raw
        )
        threshold, rule, target = _threshold_for(thresholds, role, missing_type)
        scored.loc[idx, "release_threshold"] = threshold
        scored.loc[idx, "release_rule"] = rule
        scored.loc[idx, "target_correct_within_25pct"] = target

    passes = np.isfinite(scored["gate_score_raw"]) & (
        scored["gate_score_raw"] >= scored["release_threshold"]
    )
    is_new_series = scored["missingness_type"] == "new_country_product_unit_series"
    blocked = ~np.isfinite(scored["gate_score_raw"])

    status = np.where(blocked, "blocked_missing_features", "holdout_for_review")
    status = np.where(passes & ~blocked, "released", status)
    # v1 never publishes a series nobody has ever observed: it validates at 42%
    # within 25%, so a release there would be a guess wearing a price's clothes.
    status = np.where(is_new_series, "holdout_new_series", status)
    if not config.NEW_SERIES_RELEASE_ENABLED:
        scored["release_status"] = status
    else:  # pragma: no cover - guarded off in v1
        scored["release_status"] = np.where(is_new_series & passes, "released", status)

    scored["predicted_log_median_unit_value_usd"] = scored["prediction"]
    with np.errstate(over="ignore"):
        scored["predicted_median_unit_value_usd"] = np.exp(
            scored["prediction"].to_numpy(dtype=float)
        )
    scored["thinness_stratum"] = targets_mod.thinness_stratum(
        scored["series_train_count"]
    )
    scored["run_id"] = run_id
    scored["method_id"] = config.METHOD_ID
    scored["model_version"] = f"{config.METHOD_ID}@{config.CONFIG_VERSION_DATE}"
    scored["pruning_version"] = config.PRUNING_VERSION
    scored["label_batch_version"] = label_batch_version
    scored["created_at"] = datetime.now(timezone.utc).isoformat()

    out = scored[[c for c in OUTPUT_COLS if c in scored.columns]].copy()
    config.RTCAL_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(config.SCORED_TARGETS_PARQUET, index=False)
    released = out[out["release_status"] == "released"]
    released.to_parquet(config.RELEASED_FILLS_PARQUET, index=False)

    queue = out[
        out["release_status"].isin(["holdout_for_review", "holdout_new_series"])
    ].copy()
    # Rank the queue by what a label would buy: recency, then how close the cell
    # sits to its threshold (near-misses are the cheapest wins), then thinness.
    queue["review_priority"] = (
        queue["period_index"].rank(pct=True) * 0.4
        + queue["prob_within_25pct_calibrated"].fillna(0).rank(pct=True) * 0.4
        + (1.0 - queue["series_train_count"].rank(pct=True)) * 0.2
    )
    queue.sort_values("review_priority", ascending=False).to_parquet(
        config.REVIEW_QUEUE_PARQUET, index=False
    )

    summary = {
        "run_id": run_id,
        "scored_targets": int(len(out)),
        "released": int(len(released)),
        "release_share": float(len(released) / len(out)) if len(out) else 0.0,
        "by_status": out["release_status"].value_counts().to_dict(),
        "by_missingness": out.groupby("missingness_type")["release_status"]
        .value_counts()
        .unstack(fill_value=0)
        .to_dict(orient="index"),
        "pruning": pruning_summary,
        "unmatched_countries": unmatched,
        "seconds": round(time.time() - started, 1),
    }
    (config.RTCAL_DIR / "rtcal_v1_run_summary.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    if verbose:
        print(
            f"\nscored {len(out):,}  released {len(released):,} "
            f"({summary['release_share']*100:.1f}%)  {summary['seconds']:.0f}s",
            flush=True,
        )
    return out, summary
