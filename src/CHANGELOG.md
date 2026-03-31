# Changelog

All notable changes to the template-repo branch are documented here.

## 2026-03-31 — EPU incremental fixes, publish pipeline, Ukrainian keywords

### Fixed
- **EPU incremental mode: extended indices always empty** — `get_count_stats(calculate_extended=False)` in `_run_incremental_epu` meant breadth/intensity/pairwise columns were never computed for tail rows. Changed to `True`.
- **EPU incremental mode: new sources silently excluded** — newspapers added after the initial full run (e.g., ukrinform with 9.9k articles) were missing from cached params and ignored. Now detects new sources and forces full recompute.
- **`--rebuild` wrote only last 2 months** — `append_missing_months` was used unconditionally, discarding full history on rebuild. Full mode now writes complete DataFrame directly.
- **Cutoff predating data range produced all-NaN indices** — default cutoff `2020-12-31` with Ukraine data starting 2021-11 meant empty standardization period. Now requires explicit `--cutoff` appropriate to data range.

### Added
- **`po text build --rebuild`** — CLI flag to force recalculation of params.json and cache, wired through cli.py → process.py → main.py
- **`po text publish --country`** — CLI flag to filter dashboard generation by country
- **`publish.py` fully wired** — loads topic attribution, topics EPU, and actors EPU data from `outputs/text/`, calls `generate_dashboard()` with correct arguments. `po text publish --country ukraine` now produces `small_dashboard_integrated.html`.
- **Verbose build output** — per-source article counts and date ranges, mode indicator (rebuild/auto), elapsed time per country
- **Ukrainian keywords: fuel_rationing, armed_conflicts** — added missing topic translations to `keywords/ukrainian/topics.json`

### Verified
- `po text build --country ukraine --rebuild --cutoff 2025-12-31` — 88k articles, 5 sources, full history 2021-11 to 2026-03-31, all indices populated
- `po text publish --country ukraine` — generates `outputs/text/small_dashboard_integrated.html` (182KB)

## 2026-03-31 — Text pipeline migration + ECA/Ukraine

### Added
- **src/core/** — Shared infrastructure: config, storage, state, hashing, http, logging
- **src/configs/regions.yaml** — Single source of truth for regions and countries (pacific + eca)
- **src/configs/settings.yaml** — Global paths and ancillary data config
- **src/cli.py** — Unified `po` CLI (Click): `po {fuel,text,prices} {collect,build,publish}`
- **src/text/scrapers/** — Full scraper framework migrated from dev (52 Python files)
  - Strategies: pagination, API, archive, follow_link
  - Pipelines: CSV storage, per-country cleaning (registry pattern)
  - Observability: metrics, progress, quality validation
  - Orchestration: single/multi scraper runners
- **src/text/configs/** — 142 newspaper YAML configs in region/country structure
  - `pacific/` — 29 countries, ~137 newspapers
  - `eca/ukraine/` — 5 newspapers (kyiv_independent, kyiv_post, ukrainska_pravda, ukrainska_pravda_eng, ukrinform)
- **src/text/analysis/** — EPU index calculation, sentiment, LASSO modeling
- **src/text/analysis/keywords/** — 26 languages (shared across regions)
- **src/text/plotting/** — Interactive Plotly dashboards
- **src/text/collect.py** — Collect stage wired to CLI with `--max-pages`, `--max-articles`, `--dry-run`
- **src/text/process.py** — Build stage (EPU analysis) with `--region`/`--country` filtering
- **src/text/publish.py** — Publish stage for dashboard generation
- **src/ancillary_data/** — World Bank, IMF loader stubs
- **src/fuel/** — Pipeline stubs + example configs/fetchers
- **src/prices/** — Pipeline stubs + example configs/spiders
- **docs/fuel/HOW_TO_ADD_NEW_FETCHER.md**
- **docs/text/HOW_TO_ADD_NEW_SCRAPER.md**
- **docs/prices/HOW_TO_ADD_NEW_SPIDER.md**
- **docs/ARCHITECTURE.md** — System design overview
- README.md in every subfolder (~50 lines each)

### Fixed
- Config discovery: region filtering for nested `{region}/{country}/{source}` paths
- Data paths: `data/text/{region}/{country}/{newspaper}/` (region-aware)
- Logging: per-source file logs at `logs/text/{region}/{country}/{newspaper}/`
- CLI `--max-pages`/`--max-articles` now patches `listing_strategy.max_pages` to reach ApiStrategy

### Changed
- **pyproject.toml** — `package-mode=true`, `po` entry point, reorganized dependency groups (scraping, nlp, fetching, ancillary, classification, plotting, testing)
- **regions.yaml** — Merged countries.yaml into regions.yaml as single file

### Verified
- `po text collect --region eca --max-pages 3 --max-articles 10` — all 5 Ukraine newspapers scraped
- Data lands at `data/text/eca/ukraine/{newspaper}/`
- Logs land at `logs/text/eca/ukraine/{newspaper}/{date}/`

## 2026-03-31 — Initial scaffold

### Added
- Target directory structure: `src/{core,configs,fuel,text,prices,ancillary_data,cli.py}`
- Scaffold commit with stubs, example configs, and HOW_TO docs
