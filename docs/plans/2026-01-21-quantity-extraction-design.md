# Quantity Extraction Methodology Design

**Date:** 2026-01-21
**Status:** Draft
**Module:** `src/cpi/coicopping/`

## Overview

This document defines the methodology for extracting product quantities from scraped supermarket data and calculating unit prices for CPI index construction.

## Design Principles

1. **Permissive inclusion** - Include most products, only reject clear failures
2. **Explicit exclusion** - Only exclude on contradictory signals or promotion detection
3. **Pattern-based hierarchy** - Deterministic regex matching before fallbacks
4. **Human-in-the-loop** - Manual review builds the pattern library over time

## Extraction Hierarchy

The quantity extraction follows a three-tier hierarchy:

### Tier 1: Weight/Volume

**Patterns:** `500g`, `1kg`, `250ml`, `1.5L`, `2 liters`

**Result:** Standardize to base units (kg, L) and calculate:
```
unit_value = price / standardized_amount
```

**Multiplier handling:**
- `2x185g` resolves to `370g`
- `3×500ml` resolves to `1500ml`

**Dimension exclusion:**
- If both sides of `x`/`×` have length units (mm, cm, in), treat as product dimensions and ignore
- Example: `50mm x 150mm` is ignored (dimensions, not quantity)

### Tier 2: Count Units

**Patterns:**
- Numeric + suffix: `20 pcs`, `6 pieces`, `12 pack`, `24pk`
- Multipliers: `2x6 pack` → 12 items
- Word-based: `dozen` → 12, `half dozen` → 6, `pair` → 2
- Contextual: `eggs`, `cans` → per-unit pricing

**Result:**
```
unit_value = price / count
```

### Tier 3: Fallback (Per-Item)

**Trigger:** No quantity detected from Tier 1 or Tier 2

**Result:**
```
quantity = 1
unit_value = price
```

Products are compared item-to-item over time without unit normalization.

## Exclusion Criteria

Products are excluded from the index under two conditions:

### 1. Contradictory Signals

Multiple conflicting quantities detected in the same product string.

**Examples:**
- `500g / 1kg`
- `250ml (500ml)`

**Action:** Mark as `status = "contradictory"`, exclude from index

### 2. Promotion or Bundle Detected

Keyword match indicates non-standard pricing that would distort unit price comparisons.

**Action:** Mark as `status = "promotion_or_bundle"`, exclude from index

## Promotion Detection

Keyword-based detection with global and source-specific lists.

### Global Keywords (all sources)

```
promo, promotion, bundle, combo, special offer,
buy 1 get 1, b1g1, bogo, value pack, multi-pack,
free, bonus, save, deal
```

### Source-Specific Additions

Configured per retailer to handle local language and retailer-specific terminology:

| Source | Additional Keywords |
|--------|---------------------|
| `samoa_market` | `special combo`, ... |
| `mh_online` | `weekly special`, ... |
| `thai_huot` | `โปรโมชั่น`, ... |
| `aeon_online` | `ការផ្សព្វផ្សាយ`, ... |

Source-specific keywords are stored in configuration (e.g., `string_cleaning.json` or a dedicated `promotion_keywords.json`).

## Status-Based Model

Instead of numeric confidence scores, use a status system that directly maps to inclusion/exclusion:

| Status | Meaning | Index Inclusion |
|--------|---------|-----------------|
| `resolved_weight_volume` | Tier 1 match (kg, L, etc.) | Yes |
| `resolved_count` | Tier 2 match (pcs, dozen, etc.) | Yes |
| `resolved_per_item` | Tier 3 fallback (no quantity) | Yes |
| `contradictory` | Conflicting quantities found | No |
| `promotion_or_bundle` | Promotion keyword matched | No |
| `pending_review` | Flagged for manual review | Yes (provisional) |

**Rationale:** The decision is binary (include/exclude) and the approach is permissive. The status provides auditability without the false precision of numeric scores.

## Manual Review Process

### Triggers

Products are flagged for manual review when:

1. **High-value products**
   - Appears in 5+ scrapes
   - Top 20% by price within COICOP category
   - High variance in extracted unit_value over time

2. **New patterns**
   - Quantity-like text detected but doesn't match any existing regex

### Workflow

```
1. System flags product for review
   → Logs: product_name, source, detected_text, reason_flagged

2. Human reviews flagged products (batch process, e.g., weekly)
   → Decides: valid pattern, noise, or edge case

3. If valid pattern:
   → Human writes/approves regex
   → Regex added to regex_config.py (with comment noting origin)
   → Commit to version control

4. Re-run extraction on historical data
   → Newly matched products get resolved quantities
```

### Pattern Addition Format

New patterns added to `regex_config.py` should include:

```python
# Added 2026-01-21 via manual review - handles "X sachets" pattern
r'(\d+)\s*sachets?'
```

## Complete Data Flow

```
Raw product string (e.g., "Tuna Chunks 2x185g Special")
    │
    ▼
┌─────────────────────────────────────┐
│ 1. Promotion keyword check          │
│    Match? → status = "promotion_or_bundle", EXCLUDE
└─────────────────────────────────────┘
    │ (no match)
    ▼
┌─────────────────────────────────────┐
│ 2. Tier 1: Weight/Volume regex      │
│    - Check for g, kg, ml, L, etc.   │
│    - Handle multipliers (2x185g → 370g)
│    - Skip if both sides are length units
└─────────────────────────────────────┘
    │ (match → resolved_weight_volume)
    │ (no match ↓)
    ▼
┌─────────────────────────────────────┐
│ 3. Tier 2: Count regex              │
│    - pcs, pieces, pack, dozen, pair │
│    - Contextual: eggs, cans         │
│    - Multipliers: 2x6pack → 12      │
└─────────────────────────────────────┘
    │ (match → resolved_count)
    │ (no match ↓)
    ▼
┌─────────────────────────────────────┐
│ 4. Tier 3: Fallback                 │
│    quantity = 1, unit_value = price │
│    status = "resolved_per_item"     │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 5. Contradiction check              │
│    Multiple conflicting quantities? │
│    → status = "contradictory", EXCLUDE
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 6. Flag for review (if applicable)  │
│    - High-value product?            │
│    - New unrecognized pattern?      │
│    → Add "pending_review" flag      │
└─────────────────────────────────────┘
    │
    ▼
Final output: status, quantity, unit, unit_value
```

## Output Schema

Each processed product should include:

| Field | Type | Description |
|-------|------|-------------|
| `product_name` | string | Original product name |
| `price` | float | Raw price from scrape |
| `quantity` | float | Extracted quantity (1 if fallback) |
| `unit` | string | Unit type: `kg`, `L`, `count`, `item` |
| `unit_value` | float | Price per standard unit |
| `status` | string | One of the six statuses above |
| `extraction_tier` | int | 1, 2, or 3 |
| `pending_review` | bool | Whether flagged for manual review |
| `exclusion_reason` | string | null, `contradictory`, or `promotion_or_bundle` |

## Implementation Notes

### Files to Modify

- `src/cpi/coicopping/regex_config.py` - Add new patterns, organize by tier
- `src/cpi/coicopping/extract_quantities.py` - Implement tiered extraction logic
- `src/cpi/coicopping/promotion_detection.py` - New file for promotion keyword matching
- `config/promotion_keywords.json` - Global and source-specific keyword lists

### Backward Compatibility

The new status-based system replaces the existing `usability_classifier.py` statuses. Migration path:

| Old Status | New Status |
|------------|------------|
| `resolved_mass` | `resolved_weight_volume` |
| `resolved_volume` | `resolved_weight_volume` |
| `resolved_count_food` | `resolved_count` |
| `promotion_or_bundle` | `promotion_or_bundle` (unchanged) |
| `ambiguous_quantity` | `pending_review` or `resolved_per_item` |
| `unresolved` | `resolved_per_item` |

## Success Metrics

- **Coverage:** ≥80% of products receive `resolved_*` status
- **Exclusion rate:** <10% excluded as promotions or contradictory
- **Review queue:** <5% flagged for manual review per scrape batch
- **Pattern growth:** Regex library grows by 2-5 patterns per month from reviews
