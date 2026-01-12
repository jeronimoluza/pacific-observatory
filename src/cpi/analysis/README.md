# CPI Supermarket Scrape Analysis

This folder contains documentation and code to analyze scraped supermarket price observations that have been classified into COICOP categories.

The primary goal is to assess **coverage** (by COICOP levels 1-4, by country, by supermarket/source, and over time) and **data quality** (missingness, duplicates, invalid values) using a consistent, reproducible workflow.

## Scope

- **Input data**: scraped supermarket observations (one row per observation), potentially including Wayback Machine snapshots.
- **Classification**: observations are classified into COICOP categories (level 4 `coicop_code`), with levels 1-3 derived via utility functions.
- **Primary coverage unit**: **unique `url_hash`**.
- **Time aggregation**: analyses should support grouping by `year` and `year-month`.

## Canonical dataset contract

### Required columns

The minimum columns required to run coverage/quality/distribution analysis are:

- `url_hash`
- `unit_value`
- `date`
- `coicop_code`
- `country`

### Recommended columns

These columns are strongly recommended for deeper coverage and debugging:

- `source` (supermarket/spider identifier)
- `product_name`
- `product_w_cat`
- `price` (raw scraped price, for debugging)
- `currency` (display only; currently hardcoded by country)
- `amount`
- `units`
- `coicop_title`
- `product_url`
- `product_id`
- `wayback` (0/1 indicating Wayback Machine record)

### Derived columns (standardized for analysis)

All analysis pipelines should standardize the following derived fields:

- `date_parsed`: parsed datetime version of `date`
- `month`: `YYYY-MM` derived from `date_parsed`
- `year`: `YYYY` derived from `date_parsed`
- `coicop_1digit`: COICOP division (level 1) derived from `coicop_code`
- `coicop_2digit`: COICOP group (level 2) derived from `coicop_code`
- `coicop_3digit`: COICOP class (level 3) derived from `coicop_code`
- `is_wayback`: boolean version of `wayback`

### Definitions

- **Observation**: one row = one scraped price observation at a point in time.
- **Item**: a unique `url_hash` (used as the headline denominator for coverage).
- **Coverage**: reported for both:
  - `n_items = nunique(url_hash)` (headline)
  - `n_obs = number of rows` (context)

## Reports: what we compute

All reports should be produced from the single master input file, written to a timestamped output directory, and then consumed by the Streamlit dashboard.

### A. Dataset summary

At minimum, report:

- `n_obs`
- `n_items`
- `n_countries`
- `n_sources`
- `min_date`, `max_date`
- `n_months`
- `n_coicop_1digit`, `n_coicop_2digit`, `n_coicop_3digit`, `n_coicop_4digit`

### B. COICOP coverage (levels 1-4)

Coverage tables should include:

- `n_items` (unique `url_hash`)
- `n_obs`
- `share_items` (share of items within filtered dataset)
- `share_obs` (share of observations within filtered dataset)

Recommended groupings:

- Overall by COICOP level (1, 2, 3, 4)
- `country` x COICOP level (1, 2, 3)
- `country` x `source` x COICOP level (1, 2, 3)

### C. Time coverage

Recommended groupings:

- `country` x `month`
- `source` x `month`
- `country` x `source` x `month`

Each table should include `n_items` and `n_obs`.

### D. Data quality

#### Missingness

Compute missing rates for:

- `amount` (high priority)
- `units`
- `product_url`
- `product_id`
- `coicop_title`
- `price` (raw)

Report missingness:

- overall
- by `country`
- by `source`
- by `coicop_3digit`
- by `month`

#### Duplicates

Measure duplicates at these granularities:

- duplicate `(url_hash, date_parsed, source)`
- exact duplicate rows (optional)

Policy:

- Keep all rows (auditability), but report duplicate rates and provide a duplicate listing for review.

#### Wayback vs Live

Report:

- share of observations where `is_wayback=True`
- share of items that ever appear as `is_wayback=True`
- “Wayback-only items” (items that never appear as live)

### E. unit_value distributions and outliers

Since currency is effectively hardcoded by country, distribution and outlier analysis should be performed **within country**.

#### Distribution stats

Compute (at minimum):

- `n_items`, `n_obs`
- `min`, `p1`, `p5`, `p25`, `median`, `p75`, `p95`, `p99`, `max`
- `mean`, `std`

Recommended groupings:

- `country`
- `country` x `source`
- `country` x `coicop_3digit`
- `country` x `source` x `coicop_3digit` (optional if sparse)

#### Outliers

Quantile-based outlier rule (default):

- Within each `(country, coicop_3digit)` group, flag observations with `unit_value` outside `[p1, p99]`.

Outputs should include a row-level outlier table and outlier rates by group.

## Expected outputs (report files)

Reports are written by `src/cpi/analysis/run_reports.py` to:

`data/cpi/analysis/reports/{YYYYMMDD_HHMMSS}/`

and optionally mirrored to:

`data/cpi/analysis/reports/latest/`

Output files:

- `summary.json`
- `coverage_coicop_l{1,2,3,4}_overall.csv`
- `coverage_coicop_l{1,2,3}_country.csv`
- `coverage_coicop_l{1,2,3}_country_source.csv`
- `coverage_time_country_month.csv`
- `coverage_time_source_month.csv`
- `coverage_time_country_source_month.csv`
- `quality_missingness_overall.csv`
- `quality_missingness_country.csv`
- `quality_missingness_source.csv`
- `quality_duplicates.csv`
- `quality_wayback_overall.csv`
- `quality_wayback_country_source.csv`
- `dist_unit_value_country.csv`
- `dist_unit_value_country_source.csv`
- `dist_unit_value_country_coicop_l3.csv`
- `outliers_unit_value_country_coicop_l3.csv`

## Running reports

Run from the project root:

```bash
poetry run python src/cpi/analysis/run_reports.py \
  --input data/cpi/analysis/all_countries_supermarket_prices.csv \
  --outdir data/cpi/analysis/reports
```

Architecture:

- `run_reports.py`: orchestration layer (I/O, file writing)
- `functions.py`: pure data wrangling/statistics functions
- `coicop_utils.py`: COICOP code mapping and hierarchy utilities
- `labels.py`: human-readable label mappings for countries, sources, and COICOP divisions

## Interactive dashboard

The dashboard (`plotting.py`) generates a standalone HTML file with Chart.js visualizations.

Features:

- Overview metrics (n_items, n_obs, n_countries, n_sources, date range)
- Interactive tables with radio button controls:
  - **COICOP Level**: Toggle between Level 1 (divisions), Level 2 (groups), Level 3 (classes)
  - **View Mode**: Toggle between absolute counts and percentages
- Two table views:
  - COICOP × Country
  - COICOP × Source
- Dynamic titles that update based on selected options

Generate dashboard:
```bash
poetry run python src/cpi/analysis/plotting.py
```

Output: `src/cpi/analysis/dashboard/index.html`
