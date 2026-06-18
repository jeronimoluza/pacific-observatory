import os
from pathlib import Path

# Model
MODEL_NAME = "gemini-3.1-flash-lite"
BATCH_SIZE = 15
CONCURRENCY = 1
OUTPUT_RETRIES = 3

# Paths (relative to repo root)
REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_PRICES_CSV = REPO_ROOT / "outputs" / "prices" / "raw" / "raw_prices.csv"
ENRICHED_PRICES_CSV = (
    REPO_ROOT / "outputs" / "prices" / "enriched" / "enriched_prices.csv"
)
ENRICH_DIR = REPO_ROOT / "data" / "prices" / "_enrich"
PRODUCTS_INPUT_PARQUET = ENRICH_DIR / "products_input.parquet"
PRODUCTS_PARQUET = ENRICH_DIR / "products.parquet"
MATCH_LOG_PARQUET = ENRICH_DIR / "match_log.parquet"
MATCH_FUZZY_ENABLED = False
COICOP_XLSX = ENRICH_DIR / "coicop_categories.xlsx"
COICOP_SUBCATS_JSON = (
    Path(__file__).resolve().parent / "static" / "coicop_subcategories.json"
)
CACHE_DIR = ENRICH_DIR / "cache"
ENRICHMENTS_PARQUET = CACHE_DIR / "enrichments.parquet"
FAILED_PARQUET = CACHE_DIR / "_failed.parquet"
EVAL_SET_CSV = ENRICH_DIR / "eval_set.csv"
EVAL_HISTORY_CSV = ENRICH_DIR / "eval_history.csv"

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
ENRICH_PROMPT_PATH = PROMPTS_DIR / "enrich_system.md"
TAXONOMY_PROMPT_PATH = PROMPTS_DIR / "taxonomy_system.md"

# Tier (b) — embed + cluster-resolved KNN
EMBED_BACKEND = "e5"  # "gemini" | "e5"
EMBED_MODEL_GEMINI = "gemini-embedding-001"
# Override via `E5_MODEL_PATH` env var to swap in a fine-tuned checkpoint
# (e.g. `data/prices/_enrich/_models/e5-ft-v1`). Cache keys mix this in so
# baseline and fine-tuned vectors coexist without collision.
E5_MODEL_PATH = os.environ.get("E5_MODEL_PATH", "intfloat/multilingual-e5-base")
# Override via `EMBED_DIM` env var when swapping models with a different
# output dimension (e5-base = 768, e5-large = 1024). HNSW indexes built with
# a different dim are silently incompatible — pair this env var with a
# `TIER_B_INDEX_DIR` override so old + new indexes don't collide.
EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))
EMBED_RPM = 90  # free-tier ceiling is 100/min for gemini-embedding-001
KNN_K = 5
# DEPRECATED scalar — remove after the next release. Production code reads
# KNN_SCORE_HARD_MIN[<model>] via knn_score_hard_min(); the scalar is kept
# only so external callers and old fixtures don't break in the cycle.
KNN_TAU_HIGH = 0.92
KNN_TAU_LOW = 0.85

# Per-model hard threshold for tier-b acceptance. Seeded with the current
# production e5 model at the legacy scalar's value (ADR-0005). Add a row
# before swapping in a new embedding model; knn_score_hard_min() raises if
# the active model is missing so a silent default never sneaks through.
KNN_SCORE_HARD_MIN: dict[str, float] = {
    "intfloat/multilingual-e5-base": KNN_TAU_HIGH,
    # e5-large is a larger model (1024-dim) but cosine scale is comparable;
    # start at the same threshold and tune from gold eval (2026-06-16).
    "intfloat/multilingual-e5-large": KNN_TAU_HIGH,
}


def knn_score_hard_min(model: str) -> float:
    """Per-model hard-threshold lookup. Raises KeyError on unknown model."""
    if model not in KNN_SCORE_HARD_MIN:
        raise KeyError(
            f"KNN_SCORE_HARD_MIN has no threshold for active model {model!r}; "
            "add it to config.KNN_SCORE_HARD_MIN before running tier-b"
        )
    return KNN_SCORE_HARD_MIN[model]


KNN_CLUSTER_AGREEMENT_MIN = 0.90
# Sub_label_id co-gate at query time. When coicop_code passes the hard/soft
# gate but the K neighbors that share the chosen coicop disagree on
# sub_label_id below this threshold, accept the coicop and route the row to a
# constrained tier-c call (enrich_sub_label_only) instead of writing the
# cluster's sub_label_id straight through. Initial conservative default —
# tune from match_log after collection.
KNN_SUB_LABEL_AGREEMENT_MIN = 0.90
KNN_SOFT_MAJORITY_MIN = 3  # out of K=5
KNN_BOOTSTRAP_CLUSTER_FLOOR = 150  # was 200; lowered post-sanitization to retain SG/MY indices (5k eval, 2026-06-11)
MATCH_TIER_B_ENABLED = True

# HIGH-COS override (2026-06-16). Third acceptance branch in
# accept_from_picked: a single neighbor with very-high cosine AND near-perfect
# cluster_agreement_coicop is accepted independent of the K-NN majority floor.
# Catches rare-but-clean clusters (small homogeneous cluster surrounded by
# unrelated noise) — e.g. Spring Onion @ cos=0.887, agreement=1.0, maj=2/5.
KNN_HIGH_COS_OVERRIDE_ENABLED = True
KNN_HIGH_COS_OVERRIDE_COSINE = 0.88
KNN_HIGH_COS_OVERRIDE_AGREEMENT = 0.95

# Brand-prior (2026-06-16). After tier-b returns not-accepted, if the
# normalized brand sits in the whitelist AND tier-b's top1 cosine is in the
# pre-soft band [LOW, HIGH), accept the brand's declared coicop_code and use
# tier-b's top1 sub_label_id (only when same-coicop). Reversible — a YAML
# edit removes a brand from the prior pool. Cross-checked downstream via the
# existing _tier_b_misses / _channel_outliers telemetry channels.
BRAND_PRIOR_ENABLED = True
BRAND_PRIORS_PATH = Path(__file__).resolve().parent / "static" / "brand_priors.yaml"
BRAND_PRIOR_COS_LOW = 0.80
BRAND_PRIOR_COS_HIGH = KNN_TAU_LOW  # 0.85 — hand off to soft above this

# Channel-aware KNN: over-fetch by this factor to give the channel filter
# enough candidates to keep, then keep only the same-channel ones if we have
# at least MIN_SAME_CHANNEL_KNN of them; otherwise fall through to
# cross-channel candidates (logged as cross_channel_accept=True).
KNN_CHANNEL_OVERFETCH = 4
MIN_SAME_CHANNEL_KNN = 3

TIER_B_INDEX_DIR = Path(
    os.environ.get("TIER_B_INDEX_DIR", str(ENRICH_DIR / "_tier_b_index"))
)
TIER_B_MISSES_PARQUET = ENRICH_DIR / "_tier_b_misses.parquet"
EMBED_CACHE_PATH = ENRICH_DIR / "_embed_cache.npz"

# Tier-b pool filter (Feature B, ADR-0003). Default "off" — bake-off favors
# rank_boost but the gold sample is too small to flip the production default
# without further validation. Values: "off" | "hard_drop" | "rank_boost".
TIER_B_POOL_FILTER = "off"
POOL_FILTER_BOOST = 0.05

# Channel-aware tier-c
CHANNEL_COICOP_PRIORS_PATH = (
    Path(__file__).resolve().parent / "static" / "channel_coicop_priors.yaml"
)
CHANNEL_OUTLIER_AUDIT = True
CHANNEL_OUTLIERS_PARQUET = ENRICH_DIR / "_channel_outliers.parquet"

# Tier-b kill-switch — combos with eval-measured precision below the floor
# are forced to tier-c. Static list regenerated by
# scripts/eval_5k_grades_to_killswitch.py.
TIER_B_KILLSWITCH_ENABLED = True
TIER_B_KILLSWITCH_PATH = (
    Path(__file__).resolve().parent / "static" / "tier_b_killswitch.yaml"
)

# Tier (c) — KNN-aware LLM reranker
LLM_MODEL_BASELINE = "gemini-3.1-flash-lite"
LLM_MODEL_ESCALATE = "gemini-3-pro"
LLM_TEMPERATURE = 0.0
LLM_CONFIDENCE_THRESHOLD = 0.7

# Proactive rate-limit ceilings per model (free-tier baseline). Values match
# the Google AI Studio quota panel. Override via `RATE_LIMITS_OVERRIDE_PATH`
# yaml (one model per top-level key with rpm/tpm/rpd) when on paid tier.
# Daily counters persist in `data/prices/_enrich/_rate_limits.json` so RPD
# survives process restarts.
RATE_LIMITS: dict[str, dict[str, int]] = {
    "gemini-3.1-flash-lite": {"rpm": 15, "tpm": 250_000, "rpd": 500},
    "gemini-3-pro": {"rpm": 2, "tpm": 32_000, "rpd": 50},
    "gemini-embedding-001": {"rpm": 100, "tpm": 30_000, "rpd": 1000},
}
RATE_LIMITS_STATE_PATH = ENRICH_DIR / "_rate_limits.json"
RATE_LIMITS_OVERRIDE_PATH = (
    Path(__file__).resolve().parent / "static" / "rate_limits_override.yaml"
)
# Conservative tokens-per-request estimate used at acquire time before the
# real usage is known. Truth-ed up after each call.
RATE_LIMIT_TOKEN_ESTIMATE_PER_CALL = 5_000
# Margin kept below the RPM/TPM ceiling so the bucket never lands exactly at
# the limit (server clock-skew tolerance).
RATE_LIMIT_HEADROOM_RATIO = 0.9
