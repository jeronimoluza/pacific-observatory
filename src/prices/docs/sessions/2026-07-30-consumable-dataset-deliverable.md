# 2026-07-30 — Consumable dataset deliverable (EAP F&B, curated 10k)

## Goal

Turn the classified EAP F&B price data into a small, clean, ready-to-share dataset
family and ship it as a Stata bundle. Built **in place** (worktrees off — data +
`.venv` live only in the main checkout). Prototype lives in job-tmp
`build_consumable.py` (not yet a `src/prices/build/` module). Nothing committed —
deliverables sit under gitignored `outputs/`.

## What shipped

Location: **`outputs/prices/consumable_datasets/`** — six parquets, a README, and a
Stata zip. Source: the `trusted` slice of
`data/prices/build/eap_fnb_observations.parquet`, division 01 only.

| file | grain | rows |
|---|---|---|
| `eap_fnb_products.parquet` | 1 / product (whole-history median) | 10,000 |
| `eap_fnb_latest_snapshot.parquet` | 1 / product (most-recent day) | 10,000 |
| `eap_fnb_daily.parquet` | 1 / product-day | 181,001 |
| `eap_fnb_monthly.parquet` | 1 / product-month | 31,816 |
| `eap_fnb_coicop_monthly_summary.parquet` | 1 / country·leaf·unit·month | 6,855 |
| `eap_fnb_coicop_latest_summary.parquet` | 1 / country·leaf·unit (latest) | 1,609 |

**Coverage:** 10,000 products · 173 COICOP leaves · 24 countries · 22 currencies ·
2024-03-12 → 2026-07-27.

**Zip:** `eap_fnb_datasets_stata.zip` (~5.4 MB) — every `eap_fnb_*` **except
`_products`** converted to `.dta` (**`to_stata` version=118** for Unicode CJK/Thai
names; date cols → Stata `td`) + `README.md`. Round-trip verified.

## Key design decisions

- **Real retail only.** Excluded the 3 multi-country crowd-sourced USD-basket
  aggregators (`livingcost`, `expatistan`, `mylifeelsewhere` — set
  `AGGREGATOR_SOURCES`). Drops 13 countries for which they were the sole source
  (China + small-Pacific/DPRK etc.) — all had **0 analytically-usable cells anyway**.
  Cost: −4.3% products, **0 COICOP leaves lost**. Revisit aggregators separately.
- **Positive unit values only.** `unit_value_local > 0` filter in `daily_series()`
  (drops F5 NaN "Per KG" + F6 $0 out-of-stock at the daily grain), reinforced by a
  `median_unit_value_local > 0` guard in `allocate()`. 0 non-positive/NaN UVs in any
  file.
- **`canonical_product_id`** = `sha256(country|source|coicop_code|name_norm|
  standard_unit|amount_value|count|multiplier)[:16]` — collapses per-branch URL
  fragments of the same product while parsed pack size keeps real variants apart.
  Join key across all files.
- **Daily-median collapse** — raw trusted history has ~49% same-day dupes → 1 median
  row per (product, day).

## The n_products / representativeness tradeoff (the main exploration)

Concern: `eap_fnb_coicop_monthly_summary` had **median `n_products` = 1** — most
category-months rested on a single product. Explored the allocation `CELL_FLOOR`
(min products guaranteed per (country, leaf) cell). Eligible universe is deep:
**46,328 products / 1,426 cells; 84.6% of cells have ≥2 eligible**, filling every
cell to 5 costs only 5,413 of the 10k budget — so coverage is never the binding
constraint; the median-1 was purely an allocation artifact.

Fixed the allocator first: the old proportional-with-floor did a **single-pass**
budget correction that overshot 10k under a high floor. Rewrote as **coverage-
balanced water-filling** — each cell gets `min(size, FLOOR)`, then remaining budget
proportional to size among cells with headroom; holds exactly 10k.

Floor sweep (all hold 10k, all keep 173 leaves / 24 countries / 1,426 cells —
flooring only *adds* to thin cells, never drops one):

| floor | monthly-cell median n_products | rep. distance from universe |
|---|---|---|
| 1 | 1 | **1.4%** (Japan 19% = true weight) |
| 2 | 2 | 4.6% |
| 3 | 2 | 7.3% |

**Key insight (user's):** the median-1 is *caused by month-slicing*. A **latest
cross-section** counts every product in a cell (each at its most-recent price), so
it isn't thinned by month and hits median >1 **even at floor=1**. That decoupled the
two goals:

- **Kept the monthly summary as a true time series** (singletons fine, median 1 OK).
- **Reverted allocation to floor=1** for maximum representativeness (1.4% off
  universe).
- **Added `eap_fnb_coicop_latest_summary.parquet`** as the depth deliverable:
  **median 2 products/cell, 10/leaf**, 51% of cells ≥2, max 297, full 173-leaf /
  24-country coverage.

## Schema / column changes made this session

- Renamed `consumable_*` → `eap_fnb_*`; `observations` → `daily`,
  `unit_value_summary` → `monthly`.
- Snapshot: dropped `latest_` column prefix (`latest_date`→`date`, …); removed
  `uv_log_mad`, `n_raw`, `n_urls`, `n_days`, `n_months`, `first_date`.
- `daily`: dropped `n_raw`/`n_urls` (moved to `monthly` only).
- `coicop_monthly_summary`: added `n_products` (distinct products in the cell/month).
- README rewritten shorter — schemas for snapshot / daily / monthly /
  coicop_monthly_summary / coicop_latest_summary.

## Gotchas

- Use `.venv/bin/python` — system python3.14 lacks `click`/`pandas`.
- `to_stata` needs `version=118` or CJK/Thai product names corrupt; pass datetime
  cols via `convert_dates={col: 'td'}`.
- The data-safety hook blocks `rm` under `outputs/`, so stale renamed files can't be
  self-deleted — the user cleared the old `consumable_*` copies.

## Next

- Promote job-tmp `build_consumable.py` → a real `src/prices/build/consumable.py`
  wired into `prices build` (still ~250-line prototype; watch the 500-line cap).
- Upstream parsing fixes F1–F7 remain the separate work-list
  ([[2026-07-30-upstream-parsing-fixes]]).
- Revisit whether/how to surface the excluded aggregators for the 13 dropped
  countries (a `source_class` opt-in column was proposed).

## Artifacts

- `outputs/prices/consumable_datasets/*.parquet` (6) + `README.md` +
  `eap_fnb_datasets_stata.zip`.
- Prototype: job-tmp `build_consumable.py`.
