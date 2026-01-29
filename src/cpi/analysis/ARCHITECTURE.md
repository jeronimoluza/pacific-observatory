# CPI Analysis Module Architecture

This document describes the modular architecture for the CPI analysis system, designed for modularity and maintainability while keeping files under 500 lines.

## Directory Structure

```
src/cpi/analysis/
├── __init__.py              # Public API exports
├── run_reports.py           # CLI orchestration (existing)
├── ARCHITECTURE.md          # This file
├── TASKS.md                 # Implementation tasks
├── ROADMAP.md               # Research objectives (existing)
├── README.md                # Usage documentation (existing)
│
├── core/                    # Core data operations
│   ├── __init__.py
│   ├── loading.py           # Data loading and I/O
│   ├── preprocessing.py     # Data cleaning and filtering
│   ├── coicop.py            # COICOP hierarchy utilities
│   └── matching.py          # Matched-model pair creation
│
├── indicators/              # Inflation indicators
│   ├── __init__.py
│   ├── inflation.py         # Core inflation calculations
│   ├── price_levels.py      # Price level tracking
│   ├── diffusion.py         # Breadth and diffusion indices
│   ├── distributions.py     # Distribution statistics
│   ├── volatility.py        # Volatility indices
│   └── outliers.py          # Outlier detection and flagging
│
├── microstructure/          # Price dynamics
│   ├── __init__.py
│   ├── stickiness.py        # Price spells and rigidity
│   ├── frequency.py         # Change frequency metrics
│   ├── churn.py             # Product entry/exit dynamics
│   └── replacement.py       # Replacement-driven inflation
│
├── quality/                 # Measurement quality
│   ├── __init__.py
│   ├── tier_analysis.py     # Tier-stratified indicators
│   ├── uncertainty.py       # Tier gaps and uncertainty bands
│   └── quality_adjusted.py  # Quality-adjusted headline measures
│
├── cross_country/           # Cross-country analysis
│   ├── __init__.py
│   ├── relative_prices.py   # PPP-style comparisons
│   ├── synchronization.py   # Inflation correlations
│   └── passthrough.py       # FX pass-through (optional)
│
└── reporting/               # Output generation
    ├── __init__.py
    ├── exporters.py         # CSV/Excel export utilities
    └── plotting.py          # Visualization functions (optional)
```

---

## Module Responsibilities

### `core/` — Foundation Layer

Shared utilities used by all analysis modules.

| Module | Responsibility | Key Functions | Est. Lines |
|--------|----------------|---------------|------------|
| `loading.py` | Data I/O | `load_prices()`, `save_results()` | ~100 |
| `preprocessing.py` | Filtering, transforms | `filter_usable()`, `compute_log_prices()`, `add_year_month()` | ~150 |
| `coicop.py` | COICOP hierarchy | `parse_coicop_level()`, `add_coicop_levels()`, `get_coicop_title()` | ~120 |
| `matching.py` | Time-series matching | `create_matched_pairs()`, `compute_price_changes()` | ~180 |

### `indicators/` — Core Inflation Metrics

Each module handles one family of indicators.

| Module | Responsibility | Key Functions | Est. Lines |
|--------|----------------|---------------|------------|
| `inflation.py` | Matched-model inflation | `aggregate_inflation()`, `compute_trimmed_mean()` | ~150 |
| `price_levels.py` | Price level tracking | `compute_price_levels()`, `compute_dispersion()` | ~120 |
| `diffusion.py` | Inflation breadth | `compute_diffusion()`, `compute_share_large()` | ~100 |
| `distributions.py` | Distribution stats | `compute_percentiles()`, `compute_moments()` | ~150 |
| `volatility.py` | Volatility indices | `compute_volatility()`, `compute_robust_volatility()` | ~100 |
| `outliers.py` | Anomaly detection | `compute_outlier_bounds()`, `flag_outliers()`, `compute_outlier_rates()` | ~150 |

### `microstructure/` — Price Dynamics

Product-level time-series analysis.

| Module | Responsibility | Key Functions | Est. Lines |
|--------|----------------|---------------|------------|
| `stickiness.py` | Price spells | `compute_price_spells()`, `aggregate_spells()` | ~200 |
| `frequency.py` | Change frequency | `compute_change_frequency()`, `avg_changes_per_product()` | ~100 |
| `churn.py` | Entry/exit rates | `compute_active_sets()`, `compute_churn_rates()` | ~150 |
| `replacement.py` | Replacement effects | `compare_entrant_prices()`, `compute_replacement_inflation()` | ~150 |

### `quality/` — Measurement Quality

Tier-based sensitivity analysis.

| Module | Responsibility | Key Functions | Est. Lines |
|--------|----------------|---------------|------------|
| `tier_analysis.py` | Tier-stratified metrics | `compute_by_tier()`, `tier_specific_inflation()` | ~200 |
| `uncertainty.py` | Tier gaps, sensitivity | `compute_tier_gaps()`, `compute_sensitivity()` | ~200 |
| `quality_adjusted.py` | Quality-adjusted headlines | `compute_quality_bands()`, `headline_by_quality()` | ~150 |

### `cross_country/` — Comparative Analysis

Cross-country and external driver analysis.

| Module | Responsibility | Key Functions | Est. Lines |
|--------|----------------|---------------|------------|
| `relative_prices.py` | PPP-style comparisons | `compute_relative_prices()`, `common_basket_filter()` | ~150 |
| `synchronization.py` | Inflation correlations | `compute_correlations()`, `cross_correlations()` | ~150 |
| `passthrough.py` | FX pass-through | `merge_fx_data()`, `estimate_passthrough()` | ~150 |

### `reporting/` — Output Layer

| Module | Responsibility | Key Functions | Est. Lines |
|--------|----------------|---------------|------------|
| `exporters.py` | File output | `export_csv()`, `export_excel()`, `format_results()` | ~100 |
| `plotting.py` | Visualizations | `plot_inflation_series()`, `plot_heatmap()`, `plot_distribution()` | ~300 |

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT: all_countries_supermarket_prices.csv                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ CORE LAYER                                                      │
│ ┌─────────────┐  ┌────────────────┐  ┌─────────────┐            │
│ │ loading.py  │→ │preprocessing.py│→ │ coicop.py   │            │
│ └─────────────┘  └────────────────┘  └─────────────┘            │
│                          │                                      │
│                          ▼                                      │
│                  ┌─────────────┐                                │
│                  │ matching.py │ (for matched-model analysis)   │
│                  └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ INDICATORS      │ │ MICROSTRUCTURE  │ │ QUALITY         │
│                 │ │                 │ │                 │
│ • inflation     │ │ • stickiness    │ │ • tier_analysis │
│ • price_levels  │ │ • frequency     │ │ • uncertainty   │
│ • diffusion     │ │ • churn         │ │ • quality_adj   │
│ • distributions │ │ • replacement   │ │                 │
│ • volatility    │ │                 │ │                 │
│ • outliers      │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ CROSS_COUNTRY   │
                    │                 │
                    │ • relative      │
                    │ • synchronize   │
                    │ • passthrough   │
                    └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ REPORTING LAYER                                                 │
│ ┌─────────────┐  ┌─────────────┐                                │
│ │ exporters   │  │ plotting    │                                │
│ └─────────────┘  └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT: data/cpi/analysis/results/{YYYY-MM-DD}/                 │
│ ├── coicop_lvl_1/                                               │
│ │   ├── inflation.csv                                           │
│ │   ├── price_levels.csv                                        │
│ │   └── ...                                                     │
│ ├── coicop_lvl_2/                                               │
│ ├── coicop_lvl_3/                                               │
│ └── coicop_lvl_4/                                               │
│ latest/ → symlink to most recent run                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

### 1. Pure Functions

All calculation modules (`indicators/`, `microstructure/`, `quality/`, `cross_country/`) contain **pure functions**:
- Input: pandas DataFrame
- Output: pandas DataFrame
- No side effects (no file I/O, no global state)

```python
def compute_inflation(df: pd.DataFrame, groupby_cols: list[str]) -> pd.DataFrame:
    """Compute matched-model inflation by group."""
    # Pure calculation, no I/O
    return result_df
```

### 2. Orchestration Separation

I/O and orchestration live in `run_reports.py` and `reporting/`:
- Load data once
- Call pure functions
- Save results

```python
# run_reports.py
df = load_prices(input_path)
df = preprocess(df)
inflation_df = compute_inflation(df, groupby_cols)
export_csv(inflation_df, output_path)
```

### 3. Composable Grouping

All aggregation functions accept `groupby_cols` parameter:

```python
# Flexible grouping
inflation_by_country = compute_inflation(df, ["country", "year_month"])
inflation_by_coicop = compute_inflation(df, ["country", "coicop_2", "year_month"])
```

### 4. Tier-Aware Design

Quality/tier filtering is a cross-cutting concern:

```python
# Filter before calculation
df_tier1 = filter_by_tier(df, tiers=[1])
inflation_tier1 = compute_inflation(df_tier1, groupby_cols)

# Or use quality module
inflation_by_tier = compute_by_tier(df, compute_inflation, groupby_cols)
```

### 5. File Size Limits

Each module stays under 500 lines by:
- Single responsibility per module
- Shared utilities in `core/`
- No code duplication across modules

---

## Key Data Structures

### Input DataFrame Schema

```python
{
    "url_hash": str,           # Product identifier
    "unit_value": float,       # Standardized price
    "usability_status": str,   # resolved_*, contradictory, etc.
    "extraction_tier": float,  # 1.0, 2.0, 3.0
    "coicop_code": str,        # "01.1.8.9"
    "country": str,            # "fiji", "samoa", etc.
    "date": datetime,          # Observation timestamp
    "price": float,            # Original price
    "currency": str,           # "FJD", "USD", etc.
}
```

### Matched Pairs DataFrame

Created by `matching.py`:

```python
{
    "url_hash": str,
    "year_month_t": str,       # Current period
    "year_month_t1": str,      # Previous period
    "log_price_t": float,
    "log_price_t1": float,
    "delta_p": float,          # log(p_t) - log(p_{t-1})
    "coicop_1": str,
    "coicop_2": str,
    "coicop_3": str,
    "coicop_4": str,
    "country": str,
    "extraction_tier": float,
}
```

### Aggregated Results DataFrame

Standard output format:

```python
{
    "country": str,
    "coicop_level": int,       # 1, 2, 3, or 4
    "coicop_code": str,
    "year_month": str,
    "metric_name": float,      # e.g., "inflation_mean", "volatility_std"
    # ... additional metrics
}
```

---

## CLI Interface

```bash
# Run all reports
poetry run python src/cpi/analysis/run_reports.py \
  --input data/cpi/analysis/all_countries_supermarket_prices.csv \
  --outdir data/cpi/analysis/results

# Filter by tier
poetry run python src/cpi/analysis/run_reports.py \
  --input data/cpi/analysis/all_countries_supermarket_prices.csv \
  --outdir data/cpi/analysis/results \
  --tiers 1 2

# Filter by country
poetry run python src/cpi/analysis/run_reports.py \
  --input data/cpi/analysis/all_countries_supermarket_prices.csv \
  --outdir data/cpi/analysis/results \
  --countries fiji samoa
```

---

## Testing Strategy

```
tests/cpi/analysis/
├── test_loading.py
├── test_preprocessing.py
├── test_coicop.py
├── test_matching.py
├── test_inflation.py
├── test_diffusion.py
├── test_stickiness.py
└── fixtures/
    └── sample_prices.csv
```

Each module has corresponding tests with:
- Small synthetic DataFrames
- Known expected outputs
- Edge cases (missing data, single observation, etc.)

---

## Extension Points

### Adding New Indicators

1. Create new module in appropriate subpackage
2. Implement pure function(s)
3. Add to subpackage `__init__.py`
4. Register in `run_reports.py`

### Adding New Countries

No code changes needed—data-driven by `country` column.

### Adding New COICOP Levels

Update `coicop.py` to parse additional levels.

### Adding External Data

Create new module in `cross_country/` for merging external datasets (e.g., FX rates, official CPI).
