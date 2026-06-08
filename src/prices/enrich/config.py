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
