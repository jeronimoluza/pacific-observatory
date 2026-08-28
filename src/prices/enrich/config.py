import os
from pathlib import Path

# Gemini / LLM knobs, retained for the gold-labeling workflow (codex + gemini
# dual-label → opus adjudication — currently run ad-hoc, not yet a pipeline
# module). The RATE_LIMITS block below is the matching Gemini quota config.
MODEL_NAME = "gemini-3.1-flash-lite"
# Escalation model for the gold-labeling Pass B (stronger, tighter RPD quota).
# Override per-run with `--model gemini-3.1-flash-lite` when pro is unavailable.
LLM_MODEL_ESCALATE = "gemini-3-pro"
CONCURRENCY = 1
OUTPUT_RETRIES = 3

# Paths (relative to repo root)
REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_PRICES_CSV = REPO_ROOT / "outputs" / "prices" / "raw" / "raw_prices.csv"
ENRICHED_PRICES_CSV = (
    REPO_ROOT / "outputs" / "prices" / "enriched" / "enriched_prices.csv"
)
ENRICH_DIR = REPO_ROOT / "data" / "prices" / "enrich"
PRODUCTS_INPUT_PARQUET = ENRICH_DIR / "products_input.parquet"
COICOP_XLSX = ENRICH_DIR / "coicop_categories.xlsx"
CACHE_DIR = ENRICH_DIR / "cache"
VETO_LEXICON_PARQUET = (
    REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "veto_lexicon.parquet"
)
BASIS_DENYLIST_PARQUET = (
    REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "basis_denylist.parquet"
)

# --- Classifier: (embedding → head) COICOP classification ---
# Structural regex extraction + a logistic-regression head over an ENSEMBLE of
# Qwen3-Embedding vectors of the RAW product name (normalization/canonicalization
# hurts). This replaced the retired KNN/HNSW + LLM-reranker cascade (removed
# 2026-07-24). The trained bundle carries its own derived tau; there is no
# config-level tau knob.
#
# The embedder concatenates three frozen encoders — 0.6B (1024-d) + 4B (2560-d) +
# 8B-q8 (4096-d) → 7680-d — each block L2-normalized independently, then joined
# with NO global renorm (per-block L2 is the whole trick: neither model dominates
# by raw magnitude). This concat lifts cov@98 from ~47% (single-4B) to ~63% on the
# div-01 gold.
#
# The backend is MIXED, matching the recipe that produced that number (the driver
# `embed_ensemble_blocks.sh`): the 0.6B is encoded in-process by sentence-
# transformers at seq-len 48; the 4B and 8B go through `mlx_embeddings` at seq-len
# 512 via a subprocess bridge to the sibling `.venv_mlx` (see `embedding.py`). The
# 8B only fits 16GB as an 8-bit mlx build, and only the locally-converted q8 dir
# (model_type=qwen3) loads — the HF `tierralibre/...-q8` id does NOT.
CLASSIFIER_EMBED_PROMPT = (
    "Instruct: Represent the retail product name for COICOP category "
    "classification.\nQuery: "
)
# Locally-converted 8-bit mlx build of Qwen3-Embedding-8B. Env-overridable; the
# default lives under the shared data store so it survives job/worktree teardown.
MLX_8B_MODEL_DIR = os.environ.get(
    "MLX_8B_MODEL_DIR", str(ENRICH_DIR / "_models" / "mlx" / "qwen3emb8b_q8")
)
# Ordered blocks — order is load-bearing: it fixes the column layout the trained
# head learned, so predict must reproduce it exactly. Each block declares its
# backend ("st" in-process | "mlx" subprocess), model id/path, and encode seq-len,
# plus an optional `prompt` (the instruction prefix that model wants; falls back
# to CLASSIFIER_EMBED_PROMPT, which is Qwen3's "Instruct:/Query:" form and must
# NOT be fed to non-Qwen encoders).
#
# Presets exist so an alternative encoder can be benchmarked against the same
# gold CV harness without touching the trained-bundle default. `qwen3_concat` is
# production; anything else is experimental. Select with `prices eval
# --embed-preset <name>` or `CLASSIFIER_EMBED_PRESET=<name>`. Block `tag` is the
# per-block disk-cache key, so tags must stay globally unique across presets.
CLASSIFIER_EMBED_PRESETS: dict[str, list[dict]] = {
    "qwen3_concat": [
        {
            "tag": "0p6b",
            "backend": "st",
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "seq": 48,
        },
        {"tag": "4b", "backend": "mlx", "model": "Qwen/Qwen3-Embedding-4B", "seq": 176},
        {"tag": "8b_q8", "backend": "mlx", "model": MLX_8B_MODEL_DIR, "seq": 176},
    ],
    # Single-block Qwen 0.6B (1024-d) — the size-matched reference point for any
    # 1024-d challenger, so a delta reads as encoder quality, not dimensionality.
    "qwen3_0p6b": [
        {
            "tag": "0p6b",
            "backend": "st",
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "seq": 48,
        },
    ],
    # Snowflake Arctic Embed v1 (335M, 1024-d) — ENGLISH-ONLY; expect it to fall
    # over on the ~21% CJK/Thai/Cyrillic share of div-01 gold. Arctic v1 takes no
    # instruction prefix on the document side.
    "arctic_l_v1": [
        {
            "tag": "arctic_l_v1",
            "backend": "st",
            "model": "Snowflake/snowflake-arctic-embed-l",
            "seq": 48,
            "prompt": "",
        },
    ],
    # Snowflake Arctic Embed 2.0 large (568M, 1024-d, XLM-R backbone) — the
    # multilingual v2 line; the like-for-like challenger to Qwen on this corpus.
    "arctic_l_v2": [
        {
            "tag": "arctic_l_v2",
            "backend": "st",
            "model": "Snowflake/snowflake-arctic-embed-l-v2.0",
            "seq": 48,
            "prompt": "",
        },
    ],
    # Arctic Embed 2.0 medium (305M, 768-d) — the cheap end of the v2 line. Its
    # GTE remote code defaults to xformers memory-efficient attention and asserts
    # if xformers is absent; the config_kwargs force the portable eager path.
    "arctic_m_v2": [
        {
            "tag": "arctic_m_v2",
            "backend": "st",
            "model": "Snowflake/snowflake-arctic-embed-m-v2.0",
            "seq": 48,
            "prompt": "",
            "config_kwargs": {
                "use_memory_efficient_attention": False,
                "unpad_inputs": False,
            },
        },
    ],
}
# Hybrids — the production concat with Arctic v2 large added as a fourth block,
# and the variant where Arctic replaces the weakest Qwen block (0.6B). Both reuse
# the same block tags, so they cost nothing beyond the head fit once each block's
# vectors are cached.
CLASSIFIER_EMBED_PRESETS["qwen3_concat_arctic"] = [
    *CLASSIFIER_EMBED_PRESETS["qwen3_concat"],
    *CLASSIFIER_EMBED_PRESETS["arctic_l_v2"],
]
CLASSIFIER_EMBED_PRESETS["qwen3_4b8b_arctic"] = [
    *CLASSIFIER_EMBED_PRESETS["qwen3_concat"][1:],
    *CLASSIFIER_EMBED_PRESETS["arctic_l_v2"],
]
CLASSIFIER_EMBED_ENSEMBLE = CLASSIFIER_EMBED_PRESETS[
    os.environ.get("CLASSIFIER_EMBED_PRESET", "qwen3_concat")
]
CLASSIFIER_EMBED_BATCH = int(os.environ.get("QWEN_EMBED_BATCH", "32"))
CLASSIFIER_EMBED_CACHE_DIR = ENRICH_DIR / "_embed_cache_qwen"
CLASSIFIER_DEFAULT_DIVISION = "01"  # food & non-alcoholic beverages (PoC scope)
CLASSIFIED_PARQUET = (
    CACHE_DIR / "classified.parquet"
)  # classify-stage output, keyed by input_hash

# Sibling venv (py3.12 + mlx_embeddings) the mlx blocks shell out to for encoding.
# Env-overridable because the mlx env lives outside the git worktree; production
# must set MLX_VENV_PYTHON or place `.venv_mlx` at the repo root.
MLX_VENV_PYTHON = Path(
    os.environ.get("MLX_VENV_PYTHON", str(REPO_ROOT / ".venv_mlx" / "bin" / "python"))
)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
ENRICH_PROMPT_PATH = PROMPTS_DIR / "enrich_system.md"

# Proactive rate-limit ceilings per model (free-tier baseline). Values match
# the Google AI Studio quota panel. Override via `RATE_LIMITS_OVERRIDE_PATH`
# yaml (one model per top-level key with rpm/tpm/rpd) when on paid tier.
# Daily counters persist in `data/prices/enrich/_rate_limits.json` so RPD
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
