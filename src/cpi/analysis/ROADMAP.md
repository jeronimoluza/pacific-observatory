# Analysis Roadmap & Research Objectives

## Overview: What We Are Trying to Do

This project builds a high-frequency, micro-level inflation monitoring system using online supermarket prices across multiple countries. By combining standardized unit prices, COICOP classification, and product-level time series, the system goes beyond traditional CPI-style averages to analyze:

- Product-level inflation dynamics
- Price dispersion, volatility, and tail risks
- Market stress, supply disruptions, and assortment changes
- Cross-country price level differences and synchronization
- Measurement uncertainty and data quality effects

Unlike official CPI, which is low-frequency and highly aggregated, this system leverages web-scraped microdata to:

- Detect inflation pressures earlier
- Separate intensive vs extensive margins (price changes vs entry/exit)
- Measure heterogeneity within categories
- Provide real-time, policy-relevant signals for small and open economies

The roadmap below structures the analysis from CPI-like core indicators to richer microstructure and cross-country policy insights.

---

# Section 1 — Core Monthly Inflation Indicators (Per Country)

**Goal:** Produce CPI-style, high-frequency inflation measures that are methodologically defensible and comparable across countries and COICOP levels.

## 1.1 Matched-Model Monthly Inflation

**Calculation**

For matched products (same `url_hash` in t and t−1):

```

Δp_i,t = log(unit_value_i,t) − log(unit_value_i,t−1)

```

Aggregate by:

```

(country × coicop_level × month)

```

Compute:
- Mean(Δp)
- Median(Δp)
- Trimmed mean(Δp), e.g. drop top/bottom 5%

At levels:
- COICOP 4 (fine)
- COICOP 3
- COICOP 2
- COICOP 1 (headline)

**Outputs**
- Monthly matched-model inflation series by COICOP level
- Multiple estimators (mean, median, trimmed)

---

## 1.2 Price Level Tracking (Log Unit Values)

**Calculation**

For all usable products:

```

p_i,t = log(unit_value_i,t)

```

Aggregate by:

```

(country × coicop_level × month)

```

Compute:
- Median(p)
- Mean(p)
- Q1(p), Q3(p)
- IQR(p)

**Outputs**
- Monthly price level indices by category
- Dispersion measures within categories

---

## 1.3 Inflation Breadth & Diffusion

**Calculation**

For matched products:

Indicators:
```

share_increase_t = mean(Δp_i,t > 0)
share_large10_t = mean(Δp_i,t > log(1.10))
share_large20_t = mean(Δp_i,t > log(1.20))
share_decrease_t = mean(Δp_i,t < 0)

```

By:
```

(country × coicop_level × month)

```

**Outputs**
- Diffusion indices of inflation
- Share of items with large price increases

---

# Section 2 — Price Distributions, Tails & Market Stress

**Goal:** Capture inflation risk, tail behavior, and volatility beyond averages.

## 2.1 Price Change Distributions

**Calculation**

Using Δp_i,t:

By:
```

(country × coicop_level × month)

```

Compute:
- Mean, Median
- P10, P25, P75, P90
- Skewness(Δp)
- Kurtosis(Δp)

**Outputs**
- Full distribution summaries of price changes
- Tail risk indicators

---

## 2.2 Volatility Indices

**Calculation**

Within category:

```

σ_c,t = std(Δp_i,t)

```

Robust alternatives:
```

IQR_Δp = Q75(Δp) − Q25(Δp)
MAD_Δp = median(|Δp − median(Δp)|)

```

**Outputs**
- Monthly volatility indices by category
- Stress indicators

---

## 2.3 Outlier & Anomaly Monitoring

**Calculation**

Using log prices p_i,t:

By:
```

(country × coicop_4 × month)

```

Compute:
- Q1, Q3, IQR
Flag:
```

soft_outlier: p < Q1 − 1.5*IQR or p > Q3 + 1.5*IQR
hard_outlier: p < Q1 − 3*IQR or p > Q3 + 3*IQR

```

**Outputs**
- Outlier rates by category and month
- Product-level anomaly flags

---

# Section 3 — Price Stickiness & Microstructure

**Goal:** Measure nominal rigidity and price flexibility.

## 3.1 Price Spell Analysis

**Calculation**

For each url_hash:
- Identify consecutive identical prices
- Compute:
  - Spell length
  - Time to first change

By category:
- Mean spell length
- Median spell length
- Hazard rate of price change

**Outputs**
- Price rigidity metrics by category
- Spell duration distributions

---

## 3.2 Frequency of Price Changes

**Calculation**

By:
```

(country × coicop_level × month)

```

Compute:
```

share_changed = mean(Δp_i,t ≠ 0)
avg_changes_per_product

```

**Outputs**
- Monthly price flexibility indicators
- Frequency of repricing

---

# Section 4 — Product Entry, Exit & Assortment Dynamics

**Goal:** Capture extensive margin dynamics ignored by CPI.

## 4.1 Product Churn

**Calculation**

Define:
- Active_t = set of url_hash in month t

By category:
```

entry_rate_t = |Active_t − Active_t−1| / |Active_t−1|
exit_rate_t  = |Active_t−1 − Active_t| / |Active_t−1|
net_churn_t  = entry_rate_t − exit_rate_t

```

**Outputs**
- Entry, exit, and churn rates
- Active product counts

---

## 4.2 Inflation via Product Replacement

**Calculation**

Compare:
- Mean/median price of entrants
- Mean/median price of continuers
- Mean/median price of exiting products

Test:
```

price_entrants − price_continuers

```

**Outputs**
- Replacement-driven inflation indicators
- Evidence of quality/variety effects

---

# Section 5 — Measurement Quality, Tier Sensitivity & Robustness

**Goal:** Quantify how core inflation results depend on measurement quality, and explicitly characterize uncertainty arising from heterogeneous extraction tiers.

Rather than treating tiers as simple filters, this phase treats extraction tier as an analytical dimension that interacts with inflation, volatility, and price levels. This allows the construction of quality-adjusted inflation measures and explicit uncertainty bands.

---

## 5.1 Tier-Stratified Core Indicators

**Objective:** Measure inflation, volatility, and price levels separately by extraction tier to assess how dynamics differ by measurement quality.

### Calculation

Define tier groups:
- Tier 1 only (weight/volume — highest quality)
- Tier 2 only (count-based food)
- Tier 3 only (per-item fallback)
- Tier 1 + Tier 2 (recommended operational set)
- All tiers

For each tier group, and for each:

```

(country × coicop_level × month)

```

Recompute:

**Inflation (matched products):**
```

π_tier,c,t = mean_i∈matched,tier [ log(p_i,t) − log(p_i,t−1) ]

```

**Volatility:**
```

σ_tier,c,t = std_i∈tier (Δp_i,t)

```

**Price Levels:**
```

median_p_tier,c,t = median_i∈tier [ log(p_i,t) ]

```

**Diffusion (breadth of inflation):**
```

share_increase_tier,c,t = mean_i∈tier (Δp_i,t > 0)

```

### Outputs

- Tier-specific matched-model inflation series
- Tier-specific volatility indices
- Tier-specific median price level series
- Tier-specific diffusion indicators

---

## 5.2 Tier Gaps & Measurement Uncertainty Bands

**Objective:** Explicitly measure how much results change when including lower-quality tiers, and construct uncertainty bands around inflation estimates.

### Calculation

For each:

```

(country × coicop_level × month)

```

Compute tier gaps:

**Inflation gaps:**
```

Δπ_1_vs_all = π_tier1 − π_all
Δπ_12_vs_all = π_tier1+2 − π_all

```

**Volatility gaps:**
```

Δσ_1_vs_all = σ_tier1 − σ_all

```

**Price level gaps:**
```

Δlevel_1_vs_all = median_p_tier1 − median_p_all

```

Define quality bands:
- Lower bound: Tier 1 inflation
- Upper bound: All-tier inflation
- Central estimate: Tier 1 + Tier 2

### Outputs

- Tier-based inflation uncertainty bands
- Tier gap time series by category
- Category-level sensitivity rankings

---

## 5.3 Tier Interaction with Core Dynamics

**Objective:** Test whether key inflation and stress signals are driven disproportionately by lower-quality measurements.

### Calculation

For each outcome (inflation, volatility, diffusion), estimate interaction-style summaries:

Compare dynamics across tiers:

```

corr(π_tier1, π_all)
corr(σ_tier1, σ_all)

```

Category-specific sensitivity:
```

sensitivity_c = mean_t |π_tier1,c,t − π_all,c,t|

```

Stress amplification:
```

stress_gap_c,t = σ_tier3,c,t − σ_tier1,c,t

```

Optional regression-style diagnostics (descriptive):

```

Δp_i,t = α + β1 * I(Tier2) + β2 * I(Tier3) + ε

```

run within:
```

(country × coicop_level)

```

### Outputs

- Correlation of tier-specific vs all-tier inflation
- Category sensitivity scores to tier inclusion
- Evidence of stress amplification in lower tiers

---

## 5.4 Quality-Adjusted Headline Inflation

**Objective:** Produce policy-facing inflation measures that explicitly account for measurement quality.

### Calculation

Construct three headline series:

- Conservative: Tier 1 only
- Baseline: Tier 1 + Tier 2
- Inclusive: All tiers

At COICOP 1 and 2:

```

π_conservative,t
π_baseline,t
π_inclusive,t

```

### Outputs

- Multiple headline inflation series by quality definition
- Quality-adjusted inflation ranges

---

# Section 6 — Cross-Country & External Drivers

**Goal:** Enable comparative and policy-relevant cross-country analysis.

## 6.1 Relative Price Levels (PPP-Style)

**Calculation**

For common baskets:
```

rel_price_c = median_price_country / median_price_all_countries

```

By:
```

(coicop_level × month)

```

**Outputs**
- Relative food and goods price levels
- Cross-country affordability indicators

---

## 6.2 Inflation Synchronization & Spillovers

**Calculation**

Compute correlations:
```

corr(π_countryA, π_countryB)

```

Cross-correlations for leads/lags.

**Outputs**
- Synchronization matrices
- Spillover indicators

---

## 6.3 Exchange Rate Pass-Through (Optional)

**Calculation**

With FX:
```

Δp_c,t = α + β * ΔFX_t + ε

```

By category.

**Outputs**
- FX pass-through elasticities
- Tradables vs non-tradables sensitivity
