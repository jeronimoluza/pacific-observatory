"""The release gate: rank candidate fills, calibrate, and pick a threshold.

The gate is what makes RT-CAL selective rather than merely predictive. It does
not improve any prediction; it decides which predictions are worth publishing.

Thresholds are chosen from out-of-fold scores only. Choosing them in-sample
would pick the point where the gate memorised its training rows, and the
published precision would be a description of the training set rather than a
forecast about new cells.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config
from .features import gate_feature_frame

try:  # pragma: no cover - environment probe
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.isotonic import IsotonicRegression

    SKLEARN_ERROR = None
except Exception as exc:  # pragma: no cover
    SKLEARN_ERROR = exc

MIN_GATE_TRAIN_ROWS = 1000


def within_tolerance(y_true, y_pred, tolerance=None):
    """The production correctness event: within +/-25% of the observed price."""
    tolerance = config.GATE_TOLERANCE if tolerance is None else tolerance
    with np.errstate(over="ignore"):
        ratio = np.exp(np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float))
    return (np.abs(ratio - 1.0) <= tolerance).astype(int)


def fit_gate(frame: pd.DataFrame, labels, seed=None):
    if SKLEARN_ERROR is not None:  # pragma: no cover
        raise RuntimeError(f"scikit-learn unavailable: {SKLEARN_ERROR}")
    labels = np.asarray(labels, dtype=int)
    if len(frame) < MIN_GATE_TRAIN_ROWS or len(np.unique(labels)) < 2:
        return None
    model = HistGradientBoostingClassifier(
        random_state=config.SEED if seed is None else seed, **config.GATE_PARAMS
    )
    model.fit(gate_feature_frame(frame), labels)
    return model


def score_gate(model, frame: pd.DataFrame) -> np.ndarray:
    if model is None:
        return np.full(len(frame), np.nan, dtype=float)
    return model.predict_proba(gate_feature_frame(frame))[:, 1]


def fit_calibrator(scores, labels):
    """Isotonic map from raw gate score to an honest probability.

    Reporting only -- release decisions use the raw score, because the
    thresholds were solved on raw scores and isotonic is monotone anyway.
    """
    if SKLEARN_ERROR is not None:  # pragma: no cover
        return None
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=int)
    ok = np.isfinite(scores)
    if ok.sum() < MIN_GATE_TRAIN_ROWS or len(np.unique(labels[ok])) < 2:
        return None
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit(scores[ok], labels[ok])
    return model


def apply_calibrator(model, scores):
    scores = np.asarray(scores, dtype=float)
    if model is None:
        return np.full(len(scores), np.nan, dtype=float)
    out = np.full(len(scores), np.nan, dtype=float)
    ok = np.isfinite(scores)
    out[ok] = model.predict(scores[ok])
    return out


def wilson_lower_bound(pos, n, z=1.645):
    if n <= 0:
        return -np.inf
    phat = pos / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2.0 * n)
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)
    return (center - margin) / denom


def threshold_for_precision(scores, labels, target, min_n=500, lower_bound=False):
    """Loosest score cut whose cumulative precision still clears ``target``.

    Walks down the score ranking and takes the LAST point that qualifies, i.e.
    the most coverage compatible with the precision target -- not the first,
    which would release almost nothing.

    Returns ``(threshold, n_released, achieved_precision)``; threshold is ``inf``
    when no cut qualifies, which correctly releases nothing.
    """
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=int)
    valid = np.isfinite(scores)
    scores, labels = scores[valid], labels[valid]
    if len(labels) < min_n or labels.min() == labels.max():
        return np.inf, 0, np.nan
    order = np.argsort(-scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_labels = labels[order]
    cum_pos = np.cumsum(sorted_labels)
    n = np.arange(1, len(sorted_labels) + 1)
    precision = cum_pos / n
    if lower_bound:
        quality = np.array([wilson_lower_bound(int(p), int(k)) for p, k in zip(cum_pos, n)])
    else:
        quality = precision
    eligible = (n >= min_n) & (quality >= target)
    if not eligible.any():
        return np.inf, 0, np.nan
    k = int(n[eligible][-1])
    return float(sorted_scores[k - 1]), k, float(precision[k - 1])


def calibration_error(labels, probs, bins=10):
    """Expected calibration error over equal-width probability bins."""
    labels = np.asarray(labels, dtype=float)
    probs = np.asarray(probs, dtype=float)
    ok = np.isfinite(probs) & np.isfinite(labels)
    if not ok.any():
        return float("nan")
    labels, probs = labels[ok], probs[ok]
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(probs, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        total += (m.sum() / len(probs)) * abs(labels[m].mean() - probs[m].mean())
    return float(total)


def accuracy_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    if not ok.any():
        return {k: float("nan") for k in ("within_10pct", "within_25pct", "within_50pct", "mae_log", "mape_pct")}
    diff = y_pred[ok] - y_true[ok]
    with np.errstate(over="ignore"):
        rel = np.abs(np.exp(diff) - 1.0)
    return {
        "within_10pct": float((rel <= 0.10).mean()),
        "within_25pct": float((rel <= 0.25).mean()),
        "within_50pct": float((rel <= 0.50).mean()),
        "mae_log": float(np.abs(diff).mean()),
        "mape_pct": float(rel.mean() * 100.0),
    }
