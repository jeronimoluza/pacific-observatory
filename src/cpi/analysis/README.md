# CPI Construction Using COICOP

*(Fiji – Experimental Price Index)*

## Overview

This project builds a **consumer price index (CPI)** using historical retail price data classified according to **COICOP**. Prices are aggregated following standard CPI methodology:

* **Jevons index** at the elementary aggregate (variety) level
* **Expenditure-weighted aggregation** at higher COICOP levels
* **Household Income and Expenditure Survey (HIES), Fiji** used for weights

**Scope**: This exercise reconstructs the first major component of the CPI: **Food and non-alcoholic beverages** (COICOP Division 01).

The objective is to produce transparent, reproducible price indices consistent with official statistical practice, while leveraging granular price data.

## Quick Start

To construct and validate the CPI:

```bash
# Build the CPI
poetry run python src/cpi/analysis/pipeline.py --country fiji --reference-month 2025-11

# Compare with IMF data
poetry run python src/cpi/analysis/comparison.py --country-code FJI --start-period 2024 --end-period 2026
```

See the [Execution](#execution) section below for full documentation and options.

## Data Sources

### 1. Price Data

* Web-scraped historical prices for individual product varieties
* Each observation is:

  * Time-stamped
  * Classified to a **COICOP 4-digit level variety** (eg. *Bread – 01.1.1.3*)
* Prices are matched over time at the variety level

#### Aggregation from 4-Digit to 3-Digit COICOP Level

Price data are initially classified at the **4-digit COICOP level** (e.g., *Cereals – 01.1.1.1*, *Flour of cereals – 01.1.1.2*, *Bread and bakery products – 01.1.1.3*, etc.). However, HIES expenditure weights are available only at the **3-digit COICOP level** (e.g., *Cereals and cereal products – 01.1.1*).

To align data with available weights, all 4-digit varieties are aggregated to their corresponding 3-digit parent category. For example:

| 4-Digit COICOP Code | 4-Digit Description | 3-Digit COICOP Code | 3-Digit Description |
|---|---|---|---|
| 01.1.1.1 | Cereals (ND) | 01.1.1 | Cereals and cereal products |
| 01.1.1.2 | Flour of cereals (ND) | 01.1.1 | Cereals and cereal products |
| 01.1.1.3 | Bread and bakery products (ND) | 01.1.1 | Cereals and cereal products |
| 01.1.1.4 | Breakfast cereals (ND) | 01.1.1 | Cereals and cereal products |
| 01.1.1.5 | Macaroni, noodles, couscous and similar pasta products (ND) | 01.1.1 | Cereals and cereal products |
| 01.1.1.6 | Other milled cereals and grain (ND) | 01.1.1 | Cereals and cereal products |

All articles classified at the 4-digit COICOP level are mapped to their 3-digit parent category for the computation of the Jevons index at the variety level.

### 2. Weights

* **Fiji Household Income and Expenditure Survey (HIES) 2019-20**
* Source: [Fiji Bureau of Statistics – HIES](https://www.statsfiji.gov.fj/census-surveys/household-income-and-expenditure-survey/)
* Provides expenditure shares by COICOP category at the **3-digit level**
* Expenditure shares from 2019-20 are applied directly to 2025 price indices using the **Young Index** approach (see below)

#### Weight Adjustment for "Food Away from Home"

"Food Away from Home" (4.3% of total expenditure) is not included in the CPI. Its weight is **proportionally redistributed** to the remaining food categories based on their original expenditure shares. This preserves the relative importance of each category.

**Redistribution Formula:**
$$
w_{\text{adjusted},k} = w_{\text{original},k} \times \left(1 + \frac{w_{\text{FAFH}}}{100}\right) = w_{\text{original},k} \times 1.043
$$

where:
* $w_{\text{original},k}$ = original HIES 2019-20 expenditure weight for category $k$
* $w_{\text{FAFH}}$ = weight of "Food Away from Home" (4.3%)
* $w_{\text{adjusted},k}$ = adjusted weight for category $k$ (normalized to sum to 100%)

Categories with higher original expenditure shares receive proportionally more of the reallocated weight, reflecting that "Food Away from Home" is a substitute for home-prepared food across all categories. The adjusted weights are then normalized to sum to exactly 100% and are used directly in the Young Index formula. See [redistribute_weights.py](./redistribute_weights.py) for the implementation.

## Weights Table

The table below shows the original HIES 2019-20 expenditure weights and the proportionally adjusted weights after redistributing the "Food Away from Home" weight.

| Food Breakdown | HIES 2019-20 Expenditure Weights | Proportionally Adjusted Weights | COICOP Code |
|---|---|---|---|
| Vegetables | 22.3% | 23.3% | 01.1.7 |
| Cereals | 17.8% | 18.6% | 01.1.1 |
| Meats | 16.6% | 17.35% | 01.1.2 |
| Seafood | 11.5% | 12.02% | 01.1.3 |
| Dairy | 6.3% | 6.58% | 01.1.4 |
| Oils | 5.2% | 5.43% | 01.1.5 |
| Sugars | 4.4% | 4.6% | 01.1.8 |
| Food Away from Home | 4.3% | – | – |
| Fruits | 4.1% | 4.28% | 01.1.6 |
| Other foods | 3.8% | 3.97% | 01.1.9 |
| Beverages | 3.7% | 3.87% | 01.2 |

*Source: [Fiji Household Income and Expenditure Survey (HIES) 2019-20](https://www.statsfiji.gov.fj/download/113/hies-2019-20/3847/2019-20_household_income_and_expenditure_survey.pdf), page 51*

## Methodology

### 1. Elementary Aggregates (EA)

Elementary aggregates (EAs) are defined at the **3-digit COICOP level**:

* **Food**: *Cereals and cereal products – 01.1.1*, *Live animals and meat – 01.1.2*, etc.
* **Beverages**: *Fruit and vegetable juices – 01.2.1*, *Coffee and coffee substitutes – 01.2.2*, etc.

Articles are classified at the 4-digit level but mapped to their 3-digit parent category, where the Jevons index is computed at the variety level.

All varieties within an EA are equally weighted because detailed weights to disaggregate from the 3-digit level (e.g., *01.1.1 – Cereals and cereal products*) to the 4-digit level (e.g., *01.1.1.3 – Bread*) are not available. Following the [IMF Consumer Price Index Manual](https://data.imf.org/en/datasets/IMF.STA:CPI), the 3-digit level is used as the elementary aggregate when such granular weights are unavailable.

#### Step 1: Monthly Price Averaging by Article

For each article (identified by `url_hash`), compute the **monthly average price**:

$$
\bar{p}_{i,t} = \frac{1}{n_t} \sum_{j=1}^{n_t} p_{i,j,t}
$$

where $p_{i,j,t}$ are individual price observations for article $i$ in month $t$, and $n_t$ is the number of observations in that month.

#### Step 2: Price Relatives with Matched Sample

For each article $i$ in an elementary aggregate, compute the **price relative** relative to the reference month (November 2025):

$$
r_{i,t} = \frac{\bar{p}_{i,t}}{\bar{p}_{i,0}}
$$

**Matched Sample Rule**: Only include articles in the monthly EA calculation if they have **existing prices in both the current month $t$ and the reference month (November 2025)**. Articles missing in either period are excluded from that month's calculation.

#### Step 3: Imputation for Missing Articles

If an article is missing a price in a given month (but has prices in the reference month), impute its monthly price based on the **average price change of other articles in the same 3-digit COICOP category**:

$$
\bar{p}_{i,t}^{\text{imputed}} = \bar{p}_{i,0} \times \overline{r}_{c,t}
$$

where $\overline{r}_{c,t}$ is the **average price relative** of all articles with matched prices in the same 3-digit COICOP category $c$ for month $t$:

$$
\overline{r}_{c,t} = \frac{1}{m_t} \sum_{i \in c, \text{matched}} r_{i,t}
$$

The imputed price is then used to calculate the price relative for that article: $r_{i,t}^{\text{imputed}} = \frac{\bar{p}_{i,t}^{\text{imputed}}}{\bar{p}_{i,0}}$

#### Step 4: Jevons Index Aggregation

Aggregate all price relatives (both matched and imputed) within an elementary aggregate using the **Jevons index** (geometric mean):

$$
J_{EA,t} = \exp\left(\frac{1}{n}\sum_{i=1}^{n}\ln r_{i,t}\right)
$$

where $n$ is the total number of articles in the elementary aggregate (including those with imputed prices).


### 2. Higher-Level Aggregation

Elementary aggregate indices (01.1.x level and 01.2.x level) are combined into higher COICOP levels (e.g., *Food and non-alcoholic beverages – 01*) using **HIES expenditure weights**:

$$
I_{c,t} = \sum_{k \in c} w_k \cdot J_{k,t}
$$

## Base Year and Sample Refresh

**Base Year: 2025**

The index uses **2025 as the price base year** rather than 2019-20. This choice reflects the data availability and quality:

* **Wayback Machine data (pre-November 2025)**: Sparse and limited coverage of product varieties
* **Web-scraped data (November 2025 onwards)**: Comprehensive and regularly updated, capturing the current market basket of popular and consistently available varieties

**November 2025 as Sample Refresh Period**: November 2025 marks the beginning of systematic web scraping. This period is treated as the **sample refresh point**, where the product variety sample is identified and locked for ongoing price tracking. This ensures we track the most relevant, currently available products moving forward, rather than attempting to reconstruct historical prices for potentially obsolete items from 2020.

### Connecting 2019-20 Weights to November 2025 Prices: The Young Index

To link the 2019-20 HIES expenditure weights to the November 2025 price base, we use the **Young Index** approach:

$$
I_{\text{Young},t} = \sum_{k} w_{2019-20,k} \cdot J_{k,t}
$$

where:
* $w_{2019-20,k}$ = expenditure share for category $k$ from the 2019-20 HIES (unchanged)
* $J_{k,t}$ = Jevons index for category $k$ at time $t$ (with November 2025 as base = 100)

Rather than attempting to "price-update" the 2019-20 weights using the sparse and potentially unreliable 2020 price observations, we apply the 2019-20 expenditure shares directly to the 2025 price indices. This avoids introducing additional measurement error and is consistent with IMF guidance on weight handling when historical price data is limited.

## Output

Time series of price indices by:

* **Food and non-alcoholic beverages component of the CPI** (COICOP Division 01): The aggregate price index for the entire food and beverages category, computed using the Young Index with 2019-20 HIES weights
* **Elementary Aggregate indices** (01.1.x level): Individual Jevons indices for each food subcategory (e.g., Cereals, Meats, Vegetables, Seafood, Dairy, Oils, Fruits, Sugars, Other foods, and Beverages)
* **Elementary Aggregate indices multiplied by their weights**: Weighted contribution of each elementary aggregate to the overall Food and non-alcoholic beverages CPI

All indices are expressed relative to a fixed base period (November 2025 = 100)

## Notes and Limitations

* The index is **experimental** and not an official CPI
* Retail price coverage may not fully represent household consumption
* Substitution is captured **within** elementary aggregates, but not **between** them
* Results depend on the quality and granularity of COICOP classification

## Execution

### Running the CPI Pipeline

To construct the CPI from price data:

```bash
poetry run python src/cpi/analysis/pipeline.py \
  --country fiji \
  --reference-month 2025-11 \
  --output-dir data/cpi/analysis/output
```

**Arguments:**
- `--country`: Country to filter data for (default: fiji)
- `--reference-month`: Reference month for base period, format YYYY-MM (default: 2025-11)
- `--output-dir`: Directory for output files (default: data/cpi/analysis/output)
- `--price-data`: Path to price data CSV (default: data/cpi/analysis/all_countries_supermarket_prices.csv)
- `--include-article-details`: Include article-level price relatives in output (optional)

**Output files:**
- `fiji_division_01_cpi.csv` – Main CPI index time series
- `fiji_ea_indices.csv` – Elementary aggregate indices
- `fiji_weighted_contributions.csv` – Weighted contributions by category
- `fiji_cpi_summary.txt` – Summary statistics and metadata
- `fiji_article_relatives.csv` – (optional) Article-level price relatives

### Comparing with IMF Data

To compare the constructed CPI with official IMF data (2024-2026):

```bash
poetry run python src/cpi/analysis/comparison.py \
  --constructed-cpi data/cpi/analysis/output/fiji_division_01_cpi.csv \
  --country-code FJI \
  --coicop CP01 \
  --start-period 2024 \
  --end-period 2026 \
  --output-dir data/cpi/analysis/output
```

**Arguments:**
- `--constructed-cpi`: Path to constructed Division 01 CPI CSV (default: data/cpi/analysis/output/fiji_division_01_cpi.csv)
- `--country-code`: ISO 3-letter country code for IMF data (default: FJI)
- `--coicop`: COICOP code (default: CP01 for Division 01)
- `--start-period`: Start year for IMF data (default: 2024)
- `--end-period`: End year for IMF data (default: 2026)
- `--output-dir`: Output directory for comparison results (default: data/cpi/analysis/output)

**Validation Metrics Computed:**
- **Month-over-Month (MoM) Inflation**: Pearson correlation, RMSE, bias, MAE
- **Year-over-Year (YoY) Inflation**: Same metrics for annual changes
- **3-Month Rolling Average**: Smoothed MoM inflation metrics
- **Lead-Lag Analysis**: Correlation at lags -2 to +2 months with p-values

**Output files:**
- `cpi_comparison.csv` – Merged IMF and constructed CPI with inflation rates
- `comparison_metrics.txt` – Detailed validation metrics and lead-lag analysis

## References

* ILO, IMF, OECD, Eurostat, World Bank (2020). *[Consumer Price Index Manual](https://data.imf.org/en/datasets/IMF.STA:CPI)*
* Fiji Bureau of Statistics – [Household Income and Expenditure Survey](https://www.statsfiji.gov.fj/census-surveys/household-income-and-expenditure-survey/)
