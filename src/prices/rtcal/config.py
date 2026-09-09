"""RT-CAL v1 constants, ported verbatim from ``rtcal_v1_config.yaml``.

Nothing here is tuned. Every number came out of William's validation run and a
changed value is a changed method, so treat this module as data rather than as
code you are free to adjust. The one thing that *is* expected to move is
``selected_release_thresholds.csv``, which `rtcal validate` re-estimates on each
refresh -- see ``DYNAMIC_UPDATING.md``.
"""

from __future__ import annotations

import math
from pathlib import Path

METHOD_ID = "rtcal_v1"
METHOD_NAME = "RT-CAL v1: Relative-Temporal Calibrated Selective Imputation"
PRICE_TARGET = "log_median_unit_value_usd"
SEED = 20260909
CONFIG_VERSION_DATE = "2026-09-09"
PRUNING_VERSION = "rtcal_v1_prune_20260909"

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "build"
UNIT_VALUE_SUMMARY_PARQUET = BUILD_DIR / "global_prices_unit_value_summary.parquet"

RTCAL_DIR = BUILD_DIR / "rtcal"

# Frozen reference tables live INSIDE the package, not under data/. They are
# code dependencies -- the method cannot run without them and a run must not
# depend on whether an untracked data directory happens to be populated.
# `DATA_CONTRACT.md` also forbids fetching country context at run time.
_PKG_DATA = Path(__file__).resolve().parent / "_data"
COUNTRY_CONTEXT_CSV = _PKG_DATA / "country_context_metadata.csv"

# The release policy, by contrast, is OUTPUT: `rtcal validate --promote`
# rewrites it. The packaged copy is the seed, used until a refresh supersedes it.
RELEASE_THRESHOLDS_SEED = _PKG_DATA / "selected_release_thresholds.csv"
RELEASE_THRESHOLDS_CSV = RTCAL_DIR / "selected_release_thresholds.csv"

SCORED_TARGETS_PARQUET = RTCAL_DIR / "rtcal_v1_scored_targets.parquet"
RELEASED_FILLS_PARQUET = RTCAL_DIR / "rtcal_v1_released_fills.parquet"
REVIEW_QUEUE_PARQUET = RTCAL_DIR / "rtcal_v1_holdout_review_queue.parquet"
RUN_REPORT_MD = RTCAL_DIR / "rtcal_v1_run_report.md"
MODEL_ARTIFACTS_DIR = RTCAL_DIR / "rtcal_v1_model_artifacts"
VALIDATION_DIR = RTCAL_DIR / "validation"

# ---- pruning -------------------------------------------------------------
# Five robust benchmarks on log USD price. A cell dies only when it is severe
# globally, or extreme under two independent benchmarks -- deliberately
# conservative, because a wrongly pruned observation is a silently missing
# training row.
PRUNE_BENCHMARKS = (
    # (group_col, prefix, min_count, scale_floor)
    ("product_unit_id", "global_product_unit", 80, 0.40),
    ("product_unit_period_id", "month_product_unit", 20, 0.35),
    ("region_product_unit_id", "region_product_unit", 30, 0.35),
    ("region_product_unit_period_id", "region_month_product_unit", 10, 0.35),
    ("series_id", "series", 8, 0.25),
)

GLOBAL_EXTREME_Z = 7.0
GLOBAL_EXTREME_RATIO = math.log(8.0)
GLOBAL_SEVERE_Z = 8.0
GLOBAL_SEVERE_RATIO = math.log(20.0)
MONTH_EXTREME_Z = 7.0
MONTH_EXTREME_RATIO = math.log(8.0)
REGION_EXTREME_Z = 6.5
REGION_EXTREME_RATIO = math.log(6.0)
REGION_MONTH_EXTREME_Z = 6.5
REGION_MONTH_EXTREME_RATIO = math.log(6.0)
SERIES_SPIKE_Z = 8.0
SERIES_SPIKE_RATIO = math.log(6.0)
SERIES_SPIKE_CORROBORATING_Z = 5.0

# ---- relative baseline ---------------------------------------------------
RELATIVE_BASELINE_KEYS = [
    "country",
    "period",
    "standard_unit",
    "coicop_l1_unit",
    "coicop_l2_unit",
    "coicop_l3_unit",
    "coicop_l4_unit",
    "product_unit_id",
    "country_coicop_l2_unit",
    "country_coicop_l3_unit",
    "country_coicop_l4_unit",
    "country_product_id",
]

RELATIVE_BASELINE_LAMBDAS = {
    "country": 45.0,
    "period": 35.0,
    "standard_unit": 60.0,
    "coicop_l1_unit": 50.0,
    "coicop_l2_unit": 38.0,
    "coicop_l3_unit": 28.0,
    "coicop_l4_unit": 22.0,
    "product_unit_id": 18.0,
    "country_coicop_l2_unit": 35.0,
    "country_coicop_l3_unit": 28.0,
    "country_coicop_l4_unit": 22.0,
    "country_product_id": 16.0,
}

BASELINE_ITERATIONS = 9
BASELINE_LEARNING_RATE = 0.45
BASELINE_UPDATE_CLIP = 0.9
BASELINE_TOTAL_CLIP = 3.0

# ---- residual model ------------------------------------------------------
RESIDUAL_SHRINK_LAMBDA = 6.0
RESIDUAL_FALLBACK_LEVELS = [
    "series_id",
    "country_product_id",
    "country_coicop_l4_unit",
    "country_coicop_l3_unit",
    "country_coicop_l2_unit",
    "product_unit_id",
    "coicop_l4_unit",
    "coicop_l3_unit",
    "coicop_l2_unit",
    "standard_unit",
    "period",
]

# ---- country similarity --------------------------------------------------
SIMILARITY_BANDWIDTH_KM = 3500.0
SIMILARITY_SAME_REGION = 1.75
SIMILARITY_SAME_INCOME = 1.20

# ---- gate ----------------------------------------------------------------
GATE_LABEL = "within_25pct"
GATE_TOLERANCE = 0.25
GATE_PARAMS = {
    "learning_rate": 0.06,
    "max_iter": 160,
    "max_leaf_nodes": 31,
    "l2_regularization": 0.05,
    "min_samples_leaf": 80,
}

NORMAL_GAP_TARGET = 0.80
NORMAL_GAP_STRICT_TARGET = 0.90
FORWARD_TIME_TARGET = 0.70
NEW_SERIES_RELEASE_ENABLED = False

# Fallback thresholds, used only when no re-estimated table exists yet. These
# are William's 95pct-database values and are expected to be superseded.
FALLBACK_THRESHOLDS = {
    "country_month_gap": 0.574047287241,
    "product_month_gap": 0.563260241800,
    "normal_gap_mixed": 0.574047287241,
    "future_or_latest_month_gap": 0.563027728205,
}

# ---- validation ----------------------------------------------------------
K_FOLDS = 5
FOLD_SEED = "mc_folds_v1_20260909"
FOLD_SCHEMES = (
    "fold_country_month_holdout",
    "fold_product_month_holdout",
    "fold_series_holdout",
    "fold_time_block",
    "fold_country_holdout",
    "fold_product_unit_holdout",
)
GATE_SCHEMES = ("fold_country_month_holdout", "fold_product_month_holdout", "fold_time_block")

# ---- drift, from FULL_DATASET_RUNBOOK.md --------------------------------
DRIFT_MAX_PRUNED_SHARE = 0.005
DRIFT_MAX_COUNTRY_PRUNED_SHARE = 0.05
DRIFT_MIN_NORMAL_WITHIN25 = 0.78
DRIFT_MIN_FORWARD_WITHIN25 = 0.68
DRIFT_MAX_CALIBRATION_ERROR = 0.02
DRIFT_MAX_THRESHOLD_MOVE = 0.05

THINNESS_BINS = [(0, 0), (1, 2), (3, 5), (6, 11), (12, 10**9)]
