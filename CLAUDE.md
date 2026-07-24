# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install
make dev                # poetry install --with dev && pre-commit install (full setup)
make install            # poetry install (production deps only)

# Lint / format
make lint               # ruff check src/ (read-only)
make fmt                # ruff format + ruff check --fix
make ci                 # lint + all tests (the CI gate)

# Test
make test               # pytest tests/ -v
make test-unit          # pytest tests/unit -v
make test-integration   # pytest tests/integration -v
poetry run pytest tests/prices/enrich/test_extract.py -v        # single file
poetry run pytest tests/prices/enrich/test_extract.py::test_name # single test
poetry run pytest -m unit                                        # by marker (unit|integration|slow)

# Enrich eval (classifier gold eval, coverage@precision)
make eval               # runs `python run.py prices eval` (head_eval.py)

# Docs
make docs               # jupyter-book build (opens browser)
```

## CLI Reference

The repo-local entry point is `python run.py` (defined via `run.py` → `src/cli.py`). The installed alias is `po` after `poetry install`.

**Top-level:**
```
python run.py                    # Home screen with cached pipeline snapshot
python run.py --version
python run.py status             # Compute pipeline health, write cache
python run.py list-regions       # Show region/subregion/country topology
```

**Text pipeline** (`src/text/`):
```
python run.py text collect [--region R] [-S SUBREGION] [--country C] [--source SRC]
               [--max-pages N] [--max-articles N] [--dry-run] [--rebuild]
python run.py text collect --list           # YAML-only inventory (no data reads)
python run.py text build   [--region R] [-S SUBREGION] [--country C]
               [--rebuild] [--cutoff-start-date YYYY-MM-DD] [--cutoff-end-date YYYY-MM-DD]
python run.py text publish [--region R] [-S SUBREGION] [--country C]
python run.py text status  [--region R] [-S SUBREGION] [--country C]
```

**Fuel pipeline** (`src/fuel/`):
```
python run.py fuel collect [--region R] [-S SUBREGION] [--country C] [--source SRC]
               [--dry-run] [--rebuild] [--force]
python run.py fuel build   [--region R] [-S SUBREGION] [--country C]
python run.py fuel publish [--region R] [-S SUBREGION]
```
The legacy module CLI at `python -m src.cpi.fuel_prices` is still callable but superseded by `python run.py fuel`.

**Prices pipeline** (`src/prices/`):
```
python run.py prices collect       # Scrapy spiders + per-source fetchers, unified
python run.py prices backfill      # Resumable Wayback backfill
python run.py prices common-crawl  # WARC ingest
python run.py prices process       # Enrich + COICOP classify
python run.py prices build         # EAP F&B PoC: data/prices/_build/eap_fnb_observations.parquet
python run.py prices publish       # EAP F&B PoC: outputs/prices/eap_fnb_dashboard.html
```
`build`/`publish` are scoped to the EAP food-&-beverage proof-of-concept basket; region/subregion/country flags are accepted but ignored until the basket widens.

`-S/--subregion` filters within a region. Subregion/region aggregates are built automatically when scope covers 2+ units (skipped when `--country` is specified). Invalid slugs produce an error pointing to `python run.py list-regions`.

## Architecture

Every pipeline follows `collect → build → publish` on top of `src/core/`.

### Directory map

| Directory | Status | Notes |
|---|---|---|
| `src/text/` | LIVE | Newspaper scraping, EPU index, dashboards |
| `src/fuel/` | LIVE | Per-country YAML configs, fetcher registry |
| `src/prices/` | LIVE | Scrapy + fetchers + enrich; build/publish at EAP F&B PoC scope |
| `src/cpi/` | LIVE | Supermarket CPI + legacy `fuel_prices/` module |
| `src/tourism/` | LIVE | Tourism indicators |
| `src/core/` | LIVE | Shared modules used across pipelines |
| `src/configs/` | LIVE | `regions.yaml`, `countries.yaml`, `settings.yaml` |
| `src/ancillary_data/` | LIVE | Supporting datasets |

### Core (`src/core/`)

| Module | Responsibility |
|---|---|
| `config.py` | Load YAML configs, discover pipeline sources, region/country helpers, slug validation, regions table |
| `storage.py` | Per-source paths, CSV I/O, slug utilities |
| `state.py` | Source freshness and staleness assessment |
| `hashing.py` | Observation dedup via SHA-256 |
| `http.py` | HTTP session with browser-like headers |
| `logging.py` | Structured file logging per source |

### Text/EPU (`src/text/`)

Config-driven newspaper scraping → EPU index → interactive dashboards.

```
src/text/configs/{region}/{subregion}/{country}/{source}.yaml
  → collect.py   → data/text/{region}/{subregion}/{country}/{newspaper}/news.csv
  → process.py   → outputs/text/{region}/{subregion}/{country}/epu/epu.csv
                 → outputs/text/{region}/{subregion}/_aggregate/epu/epu.csv
  → publish.py   → outputs/text/dashboard_data.json
                 → outputs/text/small_dashboard_integrated.html
```

EPU keywords live under `src/text/analysis/keywords/{language}/epu.json` (26 languages). Language resolves from the `language:` key in the source YAML → `language` column in `news.csv` → `"en"` fallback.

Build is incremental by default (reads `data/text/cache/.../params.json`); `--rebuild` forces full recompute. A new source not present in cached params triggers full recompute automatically.

### Fuel (`src/fuel/`, legacy `src/cpi/fuel_prices/`)

Per-country YAML with Pydantic validation. Fetchers expose `fetch_xxx(cutoff: date) -> pd.DataFrame`; the FETCHER_REGISTRY is built dynamically from YAML configs.

**Storage:** `data/cpi/fuel_prices/{country}/{source}/observations.csv` (legacy path retained).

### Prices (`src/prices/`)

A Scrapy project (`price_scraping/`) and standalone `fetchers/` are unified under `prices collect`. `enrich/` assigns each deduplicated product a COICOP leaf plus structured attributes via two independent jobs — **structural regex extraction + (embedding → head) classification**:

- **Structural extraction** (`extract.py` + `regex_patterns/` + `extract_patterns.py`) — deterministic regex that overlays `pricing_basis`, `amount`, `count`, `multipack`, and promo flags onto each product name. This is the stable, high-value core; do not conflate it with the classifier.
- **Classification** — an **ensemble embedding** of the *raw* product name (Qwen3-Embedding 0.6B + 4B + 8B concatenated, each block L2-normalized then joined with no global renorm; previously single-4B, e5-base → multilingual-e5-large) feeding a **logistic-regression head** that predicts the COICOP leaf. The 0.6B runs in-process via sentence-transformers; the 4B/8B via an `mlx_embeddings` subprocess bridge to the sibling `.venv_mlx` (the 8B only fits 16GB as an mlx q8). Feed raw product text to the embedder — normalization/canonicalization hurts accuracy. The `canonical_*` keys are **not** classifier inputs.

**Gold** trains and evaluates the head. The gold-growth loop: dispatch batches for targeted COICOP leaves to **codex + gemini-3.1-flash**, keep **only the rows where the two labelers agree**, and fire **opus** to adjudicate hard cases and disagreements. Canonical gold is `data/prices/enrich/gold/gold_v5_8k_final.parquet` (note: `enrich/` **without** underscore — distinct from the `_enrich/` working dir), evaluated via `prices eval` and filterable by COICOP division (food+beverages `01` for now).

`backfill/` is the resumable Wayback runner. `build/` (aggregate + basket + fx) and `publish.py` are live at EAP F&B PoC scope — `build` writes `data/prices/_build/eap_fnb_observations.parquet`, `publish` renders `outputs/prices/eap_fnb_dashboard.html` with vendored/inlined Chart.js (WB intranet blocks CDNs).

> **Migration status:** the embedding→head classifier has fully replaced the retired KNN/HNSW + LLM-reranker cascade, which was **removed** on 2026-07-24 (`stages/{enrich,tier_c,dedupe}.py`, the `tier_b/` package, `eval/{runner,gold,metrics,report}.py`, the tier-b/tier-c config block, and their scripts/tests are gone). The `prices build` step now reads the live `classified.parquet` (keyed by `input_hash`, states `narrow_source`/`classified`) rather than the retired `enrichments.parquet` cache. Any lingering `tier_b`/`tier_c`/`KNN`/`HNSW`/`consensus`/`witness` reference, plus the Gemini `gemini_classification.csv` from the separate legacy `src/cpi/coicopping/` classifier, is dead — do not treat it as current.

### Configuration system

Topology: `src/configs/regions.yaml` (region → subregion → country slug lists).
Country properties: `src/configs/countries.yaml` (slug → name, iso3, currency, languages).
Discovery: `core.config.discover_pipeline_configs()` — directories starting with `_` are skipped.

## Project skills

Project-specific workflows live under `.claude/skills/` and are invoked via the `Skill` tool when their trigger conditions match:

- `assess-newspaper-source` — vet a new newspaper URL for scraping feasibility
- `onboard-country-price-sources` — discover, scaffold, and test price sources for one country
- `onboard-region-newspapers` — batch-onboard text scrapers across a region or subregion
- `refresh-text-region` — orchestrate `text collect` across a region with stuck-source recovery
- `translate-english-keywords` — translate EPU/actors/topics keyword JSONs for a new language
- `update-fuel-crisis-policy` — refresh per-region Fuel Crisis Policy trackers and addons
- `update-fuel-price-regimes` — research and write fuel price-regime configs for Tab 1

- **Spike findings for template-repo** (prices/enrich implementation patterns, constraints, gotchas) → `Skill("spike-findings-template-repo")`

## Hard constraints

- **Data safety:** A PreToolUse hook denies destructive ops (`rm`, `rmdir`, `find -delete`)
  under `data/`/`outputs/` and asks before `mv`. Creating objects is allowed —
  the base-item skill writes staging under `data/prices/_enrich/validation_runs/`.
  Never hand-delete or overwrite existing files under `data/`/`outputs/`.
- **Git:** Never commit files under `data/`, `outputs/`, or `openspec/`; no `Co-Authored-By` lines
- **File size:** 500-line max per Python file — split before adding
- **Timestamps:** UTC only — `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- **Docs:** Don't create README files or add docstrings/comments/type annotations to code you didn't change

## Tool config

- **Linter:** Ruff (replaces black/flake8/isort), line length 100
- **Tests:** pytest with markers `unit`, `integration`, `slow`; `PYTHONPATH=src`
- **Package manager:** Poetry
