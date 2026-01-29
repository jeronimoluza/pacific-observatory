# Implementation Tasks: Phases 1–3

This document outlines the specific implementation tasks required to execute Phases 1–3 of the CPI analysis roadmap.

## Input Data Summary

**File**: `data/cpi/analysis/all_countries_supermarket_prices.csv`
**Rows**: ~258,000 observations
**Key columns**:
- `url_hash`: Unique product identifier
- `unit_value`: Standardized price (per kg/L/mt/item)
- `usability_status`: Quality classification (resolved_weight_volume, resolved_per_item, etc.)
- `extraction_tier`: 1 (weight/volume), 2 (count), 3 (per-item)
- `coicop_code`: 4-digit COICOP classification (e.g., "01.1.8.9")
- `country`: Country code
- `date`: Observation timestamp
- `price`, `currency`, `amount`, `units`, `standard_unit`

---

## Phase 1: Core Monthly Inflation Indicators

### Task 1.1: Data Loading & Preprocessing

**Objective**: Load and prepare data for inflation calculations.

- [ ] **1.1.1** Create `loading.py` module with `load_prices()` function
  - Read CSV with proper dtypes
  - Parse `date` column to datetime
  - Filter to usable observations (`usability_status` starts with "resolved")
  - Add `year_month` column (YYYY-MM format)

- [ ] **1.1.2** Create `coicop_utils.py` module
  - `parse_coicop_level(code, level)`: Extract COICOP at level 1/2/3/4
  - `add_coicop_levels(df)`: Add columns `coicop_1`, `coicop_2`, `coicop_3`, `coicop_4`

- [ ] **1.1.3** Create `preprocessing.py` module
  - `compute_log_prices(df)`: Add `log_unit_value` column
  - `filter_usable(df)`: Filter by usability_status
  - `filter_by_tier(df, tiers)`: Filter by extraction_tier

### Task 1.2: Matched-Model Monthly Inflation

**Objective**: Compute log price changes for matched products (same `url_hash` in consecutive months).

- [ ] **1.2.1** Create `matching.py` module
  - `create_matched_pairs(df)`: For each `url_hash`, create pairs (t, t-1)
  - `compute_price_changes(df)`: Calculate `delta_p = log(p_t) - log(p_{t-1})`
  - Handle gaps in time series (skip non-consecutive months)

- [ ] **1.2.2** Create `inflation.py` module
  - `aggregate_inflation(df, groupby_cols)`: Aggregate by (country, coicop_level, month)
  - Compute: mean, median, trimmed_mean (5% trim)
  - Return DataFrame with inflation estimates

- [ ] **1.2.3** Implement COICOP level aggregation
  - Run aggregation at levels 1, 2, 3, 4
  - Store results with `coicop_level` indicator column

### Task 1.3: Price Level Tracking

**Objective**: Track log price levels over time.

- [ ] **1.3.1** Add to `inflation.py`
  - `compute_price_levels(df, groupby_cols)`: Aggregate log(unit_value)
  - Compute: mean, median, Q1, Q3, IQR
  - Group by (country, coicop_level, month)

### Task 1.4: Inflation Breadth & Diffusion

**Objective**: Measure share of products with price increases/decreases.

- [ ] **1.4.1** Create `diffusion.py` module
  - `compute_diffusion(df, groupby_cols)`: From matched pairs
  - Compute:
    - `share_increase`: mean(delta_p > 0)
    - `share_decrease`: mean(delta_p < 0)
    - `share_large_10`: mean(delta_p > log(1.10))
    - `share_large_20`: mean(delta_p > log(1.20))

---

## Phase 2: Price Distributions, Tails & Market Stress

### Task 2.1: Price Change Distributions

**Objective**: Characterize full distribution of price changes.

- [ ] **2.1.1** Create `distributions.py` module
  - `compute_distribution_stats(df, groupby_cols)`: From matched pairs
  - Compute: P10, P25, P50, P75, P90, skewness, kurtosis
  - Group by (country, coicop_level, month)

### Task 2.2: Volatility Indices

**Objective**: Measure price change volatility within categories.

- [ ] **2.2.1** Add to `distributions.py`
  - `compute_volatility(df, groupby_cols)`:
  - Compute:
    - `std_delta_p`: Standard deviation of delta_p
    - `iqr_delta_p`: Q75 - Q25
    - `mad_delta_p`: Median absolute deviation

### Task 2.3: Outlier & Anomaly Monitoring

**Objective**: Flag price outliers within categories.

- [ ] **2.3.1** Create `outliers.py` module
  - `compute_outlier_bounds(df, groupby_cols)`: Compute Q1, Q3, IQR by group
  - `flag_outliers(df)`: Add columns:
    - `soft_outlier`: p < Q1 - 1.5*IQR or p > Q3 + 1.5*IQR
    - `hard_outlier`: p < Q1 - 3*IQR or p > Q3 + 3*IQR
  - `compute_outlier_rates(df, groupby_cols)`: Share of outliers by group

---

## Phase 3: Price Stickiness & Microstructure

### Task 3.1: Price Spell Analysis

**Objective**: Measure duration of constant prices.

- [ ] **3.1.1** Create `stickiness.py` module
  - `compute_price_spells(df)`: For each `url_hash`:
    - Identify consecutive periods with identical `unit_value`
    - Compute spell length (number of months)
    - Record spell start/end dates
  - Return DataFrame of spells

- [ ] **3.1.2** Add spell aggregation
  - `aggregate_spells(spells_df, groupby_cols)`:
  - Compute: mean_spell_length, median_spell_length
  - Group by (country, coicop_level)

### Task 3.2: Frequency of Price Changes

**Objective**: Measure how often prices change.

- [ ] **3.2.1** Add to `stickiness.py`
  - `compute_change_frequency(df, groupby_cols)`: From matched pairs
  - Compute:
    - `share_changed`: mean(delta_p != 0)
    - `avg_changes_per_product`: Total changes / unique products
  - Group by (country, coicop_level, month)

---

## Orchestration & Reporting

### Task 4.1: Report Generation

**Objective**: Orchestrate all computations and generate outputs.

- [ ] **4.1.1** Update `run_reports.py`
  - Call appropriate functions from each module
  - Save outputs to structured directory

- [ ] **4.1.2** Define output file structure
  - Base path: `data/cpi/analysis/results/{run_date}/` where `run_date` is YYYY-MM-DD or "latest"
  - Subdirectories by COICOP level: `coicop_lvl_1/`, `coicop_lvl_2/`, `coicop_lvl_3/`, `coicop_lvl_4/`
  - Files per subdirectory:
    - `inflation.csv`: Matched-model inflation by country/month
    - `price_levels.csv`: Price level statistics
    - `diffusion.csv`: Diffusion indices
    - `distributions.csv`: Distribution statistics
    - `volatility.csv`: Volatility indices
    - `outliers.csv`: Outlier rates
    - `spells.csv`: Spell statistics
    - `frequency.csv`: Change frequency
  - Example: `data/cpi/analysis/results/2026-01-29/coicop_lvl_2/inflation.csv`
  - Symlink `latest/` → most recent run date

### Task 4.2: Visualization (Optional)

**Objective**: Generate standard visualizations.

- [ ] **4.2.1** Create `plotting.py` module (optional)
  - Line charts for inflation time series
  - Boxplots for price distributions
  - Heatmaps for diffusion by category × month

---

## Implementation Order

1. Tasks 1.1 (loading, preprocessing, COICOP utils)
2. Tasks 1.2–1.4 (matched-model inflation, price levels, diffusion)
3. Tasks 2.1–2.3 (distributions, volatility, outliers)
4. Tasks 3.1–3.2 (spells, change frequency)
5. Tasks 4.1–4.2 (orchestration, reporting)

---

## Success Criteria

- [ ] All functions have docstrings with input/output specifications
- [ ] Unit tests cover core calculation logic
- [ ] Output CSVs match expected schema
- [ ] `run_reports.py` can execute full pipeline with single command
- [ ] Results are reproducible (deterministic outputs)
