import os
from pathlib import Path

# Model (Gemini — used by the taxonomy stage's pydantic-ai calls)
MODEL_NAME = "gemini-3.1-flash-lite"
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
# products.parquet is the coverage-census grain (read by `prices census`), a
# separate concept from the classify pipeline's per-input_hash products_input.
PRODUCTS_PARQUET = ENRICH_DIR / "products.parquet"
COICOP_XLSX = ENRICH_DIR / "coicop_categories.xlsx"
COICOP_SUBCATS_JSON = (
    Path(__file__).resolve().parent / "static" / "coicop_subcategories.json"
)
CACHE_DIR = ENRICH_DIR / "cache"
VETO_LEXICON_PARQUET = (
    REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "veto_lexicon.parquet"
)
BASIS_DENYLIST_PARQUET = (
    REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "basis_denylist.parquet"
)

# --- Classifier: (embedding → head) COICOP classification ---
# Structural regex extraction + a logistic-regression head over Qwen3-Embedding
# vectors of the RAW product name (normalization/canonicalization hurts). This
# replaced the retired KNN/HNSW + LLM-reranker cascade (removed 2026-07-24). The
# trained bundle carries its own derived tau; there is no config-level tau knob.
CLASSIFIER_EMBED_MODEL = os.environ.get("QWEN_EMBED_MODEL", "Qwen/Qwen3-Embedding-4B")
CLASSIFIER_EMBED_PROMPT = (
    "Instruct: Represent the retail product name for COICOP category "
    "classification.\nQuery: "
)
CLASSIFIER_EMBED_BATCH = int(os.environ.get("QWEN_EMBED_BATCH", "8"))
CLASSIFIER_EMBED_CACHE_DIR = ENRICH_DIR / "_embed_cache_qwen"
CLASSIFIER_DEFAULT_DIVISION = "01"  # food & non-alcoholic beverages (PoC scope)
CLASSIFIED_PARQUET = (
    CACHE_DIR / "classified.parquet"
)  # classify-stage output, keyed by input_hash

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
ENRICH_PROMPT_PATH = PROMPTS_DIR / "enrich_system.md"
TAXONOMY_PROMPT_PATH = PROMPTS_DIR / "taxonomy_system.md"

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
