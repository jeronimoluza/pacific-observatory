# PRD v1 — Standardized Unit Price System for Web-Scraped Supermarket Data

## 1. Purpose

Build a **reliable, auditable system** to transform noisy supermarket product listings into **standardized unit prices** suitable for:

* **Early inflation signals**
* **Price level comparisons across countries**

with explicit handling of ambiguity, promotions, and non-comparable products.

The system prioritizes **measurement validity over maximal coverage**, while preserving rejected data for diagnostics and future refinement.

---

## 2. Scope & Analytical Goals

### Primary Goals (Locked)

* **(C)** Support both:

  * High-frequency inflation monitoring
  * Cross-country price level analysis
* Produce **separate outputs** optimized for each use case

---

## 3. Product Coverage Rules

### 3.1 Included by Design

| Product Type                                  | Treatment      |
| --------------------------------------------- | -------------- |
| Mass-based food (kg)                          | Fully included |
| Volume-based food (liter)                     | Fully included |
| Eggs (count-based)                            | Included       |
| Staple food sold by count (e.g. bread loaves) | Included       |

---

### 3.2 Excluded by Design

| Product Type                                         | Reason                       |
| ---------------------------------------------------- | ---------------------------- |
| Non-food count goods (toys, toothbrushes, soap bars) | Not price-comparable         |
| Hygiene & household goods sold by unit               | High quality heterogeneity   |
| Promotional bundles & cartons                        | Break temporal comparability |
| Vouchers, combos, seasonal packs                     | Non-economic price signals   |

These exclusions apply **only to inflation and price-level aggregates**, not to raw storage.

---

## 4. Functional Requirements

### FR1 — Comprehensive Quantity Candidate Extraction

* Extract **all detectable quantity expressions** from product names
* Preserve:

  * value
  * unit
  * raw string
  * relative position
* Support mass, volume, length, and count units

---

### FR2 — Quantity Resolution Logic

For each product, the system must:

* Detect and resolve:

  * multiplicative structures (`24 pack x 185g`)
* Detect and flag:

  * multiple incompatible quantities
  * ranges (`9–15kg`)
  * additive constructs (`+`, `bonus`)
* Decide whether a **single, total standardized quantity** exists

---

### FR3 — Promotion Detection & Exclusion (Locked)

* Products identified as:

  * bundles
  * cartons
  * bulk promotions
* Must be explicitly flagged as `promotion_or_bundle`
* **Always excluded** from inflation and price-level datasets

---

### FR4 — Standard Unit Conversion

Canonical units:

* kg (mass)
* liter (volume)
* meter (length)
* count (only for food & eggs)

Conversions must be:

* deterministic
* documented
* centrally defined

---

### FR5 — Product Usability Classification (Required)

Every product must receive **one and only one** usability status:

| Status                | Meaning                      |
| --------------------- | ---------------------------- |
| `resolved_mass`       | Valid kg-based unit price    |
| `resolved_volume`     | Valid liter-based unit price |
| `resolved_count_food` | Valid count-based food price |
| `promotion_or_bundle` | Explicitly excluded          |
| `ambiguous_quantity`  | Conflicting quantities       |
| `unit_only_non_food`  | Excluded by design           |
| `unresolved`          | Parsing failed               |

---

### FR6 — Confidence Scoring

* Assign a confidence score ∈ [0, 1]
* Score must reflect:

  * clarity of resolution
  * reliance on defaults
  * presence of ranges or promotions
* Confidence is **not a replacement for usability status**

---

### FR7 — Unit Price Computation Rules

* Unit price computed **only for resolved products**
* No silent fallback (e.g. default unit = 1) for unresolved cases
* Raw price always preserved

---

### FR8 — COICOP Classification (Locked)

* All products are classified to COICOP (2018)
* Classification is **orthogonal** to quantity resolution
* COICOP does **not override usability decisions**

---

## 5. Outputs

### 5.1 Core Outputs

#### A. Inflation & Price-Level Dataset

Includes only:

* `resolved_mass`
* `resolved_volume`
* `resolved_count_food`

With:

* standardized unit price
* confidence score
* COICOP code
* country, source, date

---

#### B. Full Parsed Dataset

Includes:

* all products
* all statuses
* raw quantities
* rejection reasons

Used for:

* audits
* diagnostics
* future model improvement

---

## 6. Non-Goals (Explicit)

* Inferring consumption weights
* Modeling demand or supply
* Adjusting for quality changes beyond exclusion
* Maximizing product coverage
* ML-based quantity inference (v1)

---

## 7. Design Principles (Locked)

1. **Comparability > Coverage**
2. **Explicit rejection > silent error**
3. **Deterministic logic first**
4. **Auditability by default**
5. **Separation of parsing, resolution, and classification**

---

## 8. Success Metrics (Provisional)

### Technical

* ≥ 30–40% of food products yield high-confidence resolved prices
* 0% of promotions included in inflation aggregates
* 0 silent defaults in unresolved cases

### Analytical

* Inflation trends stable under rule perturbations
* No visible holiday-driven price spikes
* Directional consistency with official CPI where available

---

## 9. Known Open Questions (Deferred, Not Blocking v1)

* Minimum confidence threshold for inclusion
* Handling of borderline food count goods (e.g. snack packs)
* Country-specific overrides for traditional units
* Long-term role of ML for hard cases
