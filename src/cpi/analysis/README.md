# CPI Construction Using COICOP

*(Fiji – Experimental Price Index)*

## Overview

This project builds a **consumer price index (CPI)** using historical retail price data classified according to **COICOP**. Prices are aggregated following standard CPI methodology:

* **Jevons index** at the elementary aggregate (variety) level
* **Expenditure-weighted aggregation** at higher COICOP levels
* **Household Income and Expenditure Survey (HIES), Fiji** used for weights

**Scope**: This exercise reconstructs the first major component of the CPI: **Food and non-alcoholic beverages** (COICOP Division 01).

The objective is to produce transparent, reproducible price indices consistent with official statistical practice, while leveraging granular price data.

---

## Data Sources

### 1. Price Data

* Historical prices for individual product varieties
* Each observation is:

  * Time-stamped
  * Classified to a **COICOP variety / elementary aggregate**
* Prices are matched over time at the variety level

### 2. Weights

* **Fiji Household Income and Expenditure Survey (HIES) 2019-20**
* Source: [Fiji Bureau of Statistics – HIES](https://www.statsfiji.gov.fj/census-surveys/household-income-and-expenditure-survey/)
* Provides expenditure shares by COICOP category
* Expenditure shares from 2019-20 are applied directly to 2025 price indices using the **Young Index** approach (see below)

---

## Base Year and Sample Refresh

**Base Year: 2025**

The index uses **2025 as the price base year** rather than 2019-20. This choice reflects the data availability and quality:

* **Wayback Machine data (pre-November 2025)**: Sparse and limited coverage of product varieties
* **Web-scraped data (November 2025 onwards)**: Comprehensive and regularly updated, capturing the current market basket of popular and consistently available varieties

**November 2025 as Sample Refresh Period**: November 2025 marks the beginning of systematic web scraping. This period is treated as the **sample refresh point**, where the product variety sample is identified and locked for ongoing price tracking. This ensures we track the most relevant, currently available products moving forward, rather than attempting to reconstruct historical prices for potentially obsolete items from 2020.

### Connecting 2019-20 Weights to 2025 Prices: The Young Index

To link the 2019-20 HIES expenditure weights to the 2025 price base, we use the **Young Index** approach:

$$
I_{\text{Young},t} = \sum_{k} w_{2019-20,k} \cdot J_{k,t}
$$

where:
* $w_{2019-20,k}$ = expenditure share for category $k$ from the 2019-20 HIES (unchanged)
* $J_{k,t}$ = Jevons index for category $k$ at time $t$ (with 2025 as base = 100)

**Rationale**: Rather than attempting to "price-update" the 2019-20 weights using the sparse and potentially unreliable 2020 price observations, we apply the 2019-20 expenditure shares directly to the 2025 price indices. This avoids introducing additional measurement error and is consistent with IMF guidance on weight handling when historical price data is limited.

---

## Methodology

### 1. Elementary Aggregates (EA)

Elementary aggregates are defined at the **01.1.x level** for food (e.g. *Cereals and cereal products – 01.1.1*, *Live animals, and meat and other parts of slaughtered land animals – 01.1.2*, etc.), and at the **01.2.x level** for beverages (e.g. *Fruit and vegetable juices – 01.2.1.0, *Coffee and coffee substitutes – 01.2.2.0, etc.).

For each elementary aggregate:

1. Collect all product varieties classified to each COICOP category
2. Compute price relatives for each variety:
   $$
   r_{i,t} = \frac{p_{i,t}}{p_{i,0}}
   $$

3. Aggregate using the **Jevons index** (geometric mean of price relatives):
   $$
   J_{EA,t} = \exp\left(\frac{1}{n}\sum_{i=1}^{n}\ln r_{i,t}\right)
   $$

All varieties within an EA are equally weighted. This approach is used because detailed weights to aggregate from the 01.1.1.x level (e.g. *Bread – 01.1.1.3*) to the 01.1.1 level are not available. Following the [IMF Consumer Price Index Manual](https://data.imf.org/en/datasets/IMF.STA:CPI), the 01.1.x level is used as the elementary aggregate when such granular weights are unavailable.

---

### 2. Higher-Level Aggregation

Elementary aggregate indices (01.1.x level and 01.2.x level) are combined into higher COICOP levels (e.g. *Food and non-alcoholic beverages – 01) using **HIES expenditure weights**:

$$
I_{c,t} = \sum_{k \in c} w_k \cdot J_{k,t}
$$

---

## Weights

The weights are based on the 2019-20 HIES expenditure weights. "Food Away from Home" is not included in the CPI, and its weight will be equally distributed to the remaining categories.

| Food Breakdown | Expenditure Weights | COICOP Code |
|---|---|---|
| Vegetables | 22.3% | 01.1.7 |
| Cereals | 17.8% | 01.1.1 |
| Meats | 16.6% | 01.1.2 |
| Seafood | 11.5% | 01.1.3 |
| Dairy | 6.3% | 01.1.4 |
| Oils | 5.2% | 01.1.5 |
| Sugars | 4.4% | 01.1.8 |
| Food Away from Home | 4.3% | – |
| Fruits | 4.1% | 01.1.6 |
| Other foods | 3.8% | 01.1.9 |
| Beverages | 3.7% | 01.2 |

## Output

Time series of price indices by:

* **Food and non-alcoholic beverages component of the CPI** (COICOP Division 01): The aggregate price index for the entire food and beverages category, computed using the Young Index with 2019-20 HIES weights
* **Elementary Aggregate indices** (01.1.x level): Individual Jevons indices for each food subcategory (e.g., Cereals, Meats, Vegetables, Seafood, Dairy, Oils, Fruits, Sugars, Other foods, and Beverages)
* **Elementary Aggregate indices multiplied by their weights**: Weighted contribution of each elementary aggregate to the overall Food and non-alcoholic beverages CPI

All indices are expressed relative to a fixed base period (2025 = 100)

---

## Notes and Limitations

* The index is **experimental** and not an official CPI
* Retail price coverage may not fully represent household consumption
* Substitution is captured **within** elementary aggregates, but not **between** them
* Results depend on the quality and granularity of COICOP classification

---

## References

* ILO, IMF, OECD, Eurostat, World Bank (2020). *[Consumer Price Index Manual](https://data.imf.org/en/datasets/IMF.STA:CPI)*
* Fiji Bureau of Statistics – [Household Income and Expenditure Survey](https://www.statsfiji.gov.fj/census-surveys/household-income-and-expenditure-survey/)
