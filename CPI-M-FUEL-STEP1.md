# CPI Migration Fuel Step 1

## Goal

Bring `src/cpi/fuel_prices/` into `cpi-migration` as a preserved baseline and use it to define how `price-atlas` should absorb a proven East Asia & Pacific fuel reconstruction system.

This step is about stabilization and planning, not redesign.

## Step 1 Outcome

At the end of Step 1 we should have:

1. The imported `src/cpi/fuel_prices/` module present on `cpi-migration`.
2. A clear inventory of what belongs to collection, reconstruction, normalization, analysis, and publishing.
3. A list of temporary/runtime artifacts that should not become long-term repository structure.
4. A documented boundary between reusable reconstruction patterns and fuel-specific business logic.
5. A concrete follow-up plan for extracting shared `price-atlas` interfaces without changing behavior yet.

## Current Baseline

The imported module already contains:

- a registry of source fetchers in `src/cpi/fuel_prices/fetchers/__init__.py`
- incremental CLI orchestration in `src/cpi/fuel_prices/main.py`
- canonical output locations in `src/cpi/fuel_prices/constants.py`
- fetch-state persistence and deduplication in `src/cpi/fuel_prices/loader.py`
- visualization and audit tooling in `src/cpi/fuel_prices/visualize.py`, `src/cpi/fuel_prices/visualize_policy.py`, `src/cpi/fuel_prices/audit_csv.py`, and `src/cpi/fuel_prices/audit_ocr.py`
- mixed fetch modes across countries: API, HTML, PDF, OCR, and multi-source fusion

This makes `fuel_prices` the strongest existing example of a topic-specific reconstruction pipeline in the repo.

## Step 1 Scope

Included in Step 1:

- preserve the imported `src/cpi/fuel_prices/` tree as the migration baseline
- document its moving parts and outputs
- identify repository cleanup candidates and runtime-only folders
- identify which patterns are generic enough for the future `reconstruct` layer
- identify which parts are fuel-topic specific and should remain topic-local

Not included in Step 1:

- renaming `fuel_prices` to `price-atlas`
- changing output contracts under `data/`
- merging fuel logic with `price_scraping`
- rewriting fetchers into a new framework
- changing production consumers or dashboards

## Temporary And Runtime Folders To Review

Imported or referenced tmp folders that may not belong in the long-term baseline:

- `src/cpi/fuel_prices/fetchers/_to_mted_tmp/` — currently tracked; contains OCR/PDF intermediate artifacts for Tonga and is the strongest candidate to remove from versioned source control later
- `src/cpi/fuel_prices/fetchers/_ws_mof_tmp/` — runtime tmp directory referenced by Samoa OCR flow in `src/cpi/fuel_prices/fetchers/pacific_islands.py`
- `src/cpi/fuel_prices/fetchers/_vn_plx_tmp/` — runtime tmp directory referenced by Vietnam OCR flow in `src/cpi/fuel_prices/fetchers/vietnam.py`
- `_cn_ndrc_tmp/` — runtime tmp directory referenced by the China fetcher in `src/cpi/fuel_prices/fetchers/china.py`; currently appears outside the module in the repo root
- `_cn_ndrc_tmp_test/` — untracked repo-root test temp directory already present in the worktree

Step 1 should not delete these automatically. Even when we believe they are not needed long-term, we should preserve them temporarily and review them later before deletion, especially if they were produced while developing spiders or collection software.

Step 1 should classify them as:

- tracked legacy temp artifact
- runtime temp directory
- local debug/test temp directory
- possible source evidence or development artifact to preserve temporarily

The Step 1 action is quarantine and classification, not cleanup by deletion.

## Functional Decomposition

### 1. Collect / Reconstruct

This is the strongest part of the module today.

- fetchers recover observations from official APIs, web pages, PDF notices, and OCR-heavy image sources
- `FETCHER_REGISTRY` plus per-source fallback dates already provides an execution model for incremental recovery
- `SOURCE_META` in many fetchers already behaves like embedded source documentation

### 2. Normalize

Normalization exists, but it is interleaved with loader and visualization logic.

- canonical columns live in `src/cpi/fuel_prices/constants.py`
- deduplication is centered on `observation_hash`
- country/product cleanup rules live in `src/cpi/fuel_prices/loader.py`

Step 1 should document this as existing normalization logic, but not extract it yet.

### 3. Analyze / Publish

The module already has a practical downstream layer:

- `eap_fuel_prices.csv`
- `eap_fuel_prices_secondary.csv`
- `commodity_prices.csv`
- HTML outputs driven by the visualizers

Step 1 should treat these as current published/consumer-facing artifacts, even if their future `price-atlas` contract changes.

## Step 1 Deliverables

1. Imported `src/cpi/fuel_prices/` baseline on `cpi-migration`
2. Inventory of fetchers, outputs, dependencies, and temp/runtime folders
3. Mapping of code into:
   - reusable reconstruction patterns
   - fuel-specific topic logic
   - downstream visualization/publishing logic
4. Explicit follow-up tasks for Step 2

## Step 2 Candidates Enabled By This Step

Once Step 1 is complete, the next fuel migration step can:

1. isolate runtime tmp handling from versioned source files
2. convert `SOURCE_META` into a more formal source catalog contract
3. define canonical `reconstructed_observation` and `published_series` contracts for fuel data
4. separate generic reconstruction helpers from fuel-topic fetchers
5. identify which visualization logic should remain topic-local versus move to shared publishing utilities
6. define a later cleanup/review procedure for tmp and development artifacts without deleting them during migration

## Risks

- importing the module as-is also imports legacy temp artifacts, especially `src/cpi/fuel_prices/fetchers/_to_mted_tmp/`
- normalization logic is spread across orchestration, loader, and visualization, which can blur stage boundaries
- OCR and PDF dependencies (`tesseract`, `pdfplumber`) increase operational complexity and should be made explicit in later contracts
- some runtime temp paths are not module-local, which complicates cleanup and reproducibility
- artifacts that look disposable may actually capture development evidence from building OCR and fetch flows, so premature deletion would lose context

## Exit Criteria

Step 1 is complete when:

- `src/cpi/fuel_prices/` is available on `cpi-migration`
- temporary/runtime folder candidates are explicitly identified
- temporary/runtime folder candidates are marked for preservation and later review rather than immediate deletion
- the module's stage boundaries are documented
- a Step 2 extraction/refactor list exists without changing current behavior
