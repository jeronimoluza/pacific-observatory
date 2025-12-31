# CPI Construction Using COICOP

*(Fiji – Experimental Price Index)*

## Overview

This project builds a **consumer price index (CPI)** using historical retail price data classified according to **COICOP**. Prices are aggregated following standard CPI methodology:

* **Jevons index** at the elementary aggregate (variety) level
* **Expenditure-weighted aggregation** at higher COICOP levels
* **Household Income and Expenditure Survey (HIES), Fiji** used for weights

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

* **Fiji Household Income and Expenditure Survey (HIES)**
* Provides expenditure shares by COICOP category
* Weights are treated as **base-period (Laspeyres) weights**

---

## Methodology

### 1. Elementary Aggregates (EA)

For each COICOP elementary aggregate (e.g. *Bread – 01.1.1.3*):

1. Compute price relatives for each variety:
   [
   r_{i,t} = \frac{p_{i,t}}{p_{i,0}}
   ]

2. Aggregate using the **Jevons index** (geometric mean):
   [
   J_{EA,t} = \exp\left(\frac{1}{n}\sum_{i=1}^{n}\ln r_{i,t}\right)
   ]

All varieties within an EA are equally weighted.

---

### 2. Higher-Level Aggregation

Elementary aggregate indices are combined into higher COICOP levels (e.g. *Cereals and cereal products – 01.1.1*) using **HIES expenditure weights**:

[
I_{c,t} = \sum_{k \in c} w_k \cdot J_{k,t}
]

This process is repeated hierarchically up to the desired COICOP level.

---

## Output

* Time series of price indices by:

  * COICOP subclass
  * Class
  * Group
  * Division (optional)
* Indices are expressed relative to a fixed base period

---

## Notes and Limitations

* The index is **experimental** and not an official CPI
* Retail price coverage may not fully represent household consumption
* Substitution is captured **within** elementary aggregates, but not **between** them
* Results depend on the quality and granularity of COICOP classification

---

## References

* ILO, IMF, OECD, Eurostat, World Bank (2020). *Consumer Price Index Manual*
* Fiji Bureau of Statistics – Household Income and Expenditure Survey
