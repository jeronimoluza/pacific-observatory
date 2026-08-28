# Prices — Skills

The `.claude/skills/` entries that operate on the prices pipeline, and — just as
important — which ones describe the **retired** KNN cascade and must not be
trusted for architecture. Skills auto-surface as agent capabilities, so a stale
one is a live drift risk. See `GLOSSARY.md → Retired — do not use` for the
term-by-term mapping.

## Current — safe to run

| Skill | What it does |
|---|---|
| `onboard-price-sources` | Depth-audit existing coverage, then discover, scaffold, and end-to-end-test new price sources (platform/marketplace-first discovery → probing → spider/fetcher + YAML under `src/prices/configs/` → automated test → coverage report). Scopes to one country, a region, a commodity gap, or a single URL. Renamed from `onboard-country-price-sources` 2026-08-04 — discovery is not a per-country activity. |
| `iterate-retailer-unit-values` | Iterate the **tier-a** unit-value regex (`pricing_basis`/`amount`/`count`/`multiplier`) toward ~95% exact-tuple accuracy: Sonnet labels fresh retailer rows into a persistent bank, scores `extract.py`, drives one narrow regex fix per round, commit-or-revert. Operates on the surviving structural extractor only. |

## Partial — mixed current/retired

| Skill | Caveat |
|---|---|
| `spike-findings-template-repo` | Enrich implementation blueprint, auto-loaded during `prices/enrich` work (referenced in `CLAUDE.md`). Its **tier-a retailer unit-value loop** guidance is current; its **tier-b query-side brand cleaner** half is cascade-era and dead. Take the tier-a parts, ignore the tier-b parts. |

## Retired — do NOT trust their architecture claims

These four still narrate the KNN/HNSW tier-b/tier-c cascade, `base_items` /
`gazetteer` / CANDIDATE→GREEN, W5 consensus/witness, or CLI verbs that **do not
exist** (`prices classify`, `prices iterate`, `prices classify-corpus`). The live
classify path is only `extract()` + `(embedding → head)` + vetoes. `base_item`
appears **0×** in `src/`. Retiring or rewriting these is an open backlog item
(see `sessions/2026-07-27-docs-consolidation.md`, item #2).

| Skill | Retired concepts it presents as current |
|---|---|
| `classify-base-item-prices` | `base_items.parquet`, `gazetteer.parquet`, `validation_runs/`, CANDIDATE→GREEN, `prices classify` verb |
| `diagnose-prices-cascade` | tier-a/tier-b/tier-c cascade, tier-b KNN, tier-c Gemini reranker |
| `improve-prices-cascade` | tier-b KNN thresholds, oracle labels, `_gold_v3_misses.csv`, `prices iterate`, ADR-0005 |
| `resolve-price-conflicts` | W5 consensus/witness verdict loop, `prices classify-corpus`, `conflicts.parquet`, gazetteer flywheel |

## Not prices

`assess-newspaper-source`, `assess-n-fix`, `onboard-region-newspapers`,
`refresh-text-region`, `refresh-all-regions`, `text-storage`,
`translate-english-keywords` belong to **text**; `update-fuel-crisis-policy`,
`update-fuel-price-regimes`, `refresh-fuel-dashboards` belong to **fuel**. They
get their own `src/<pipeline>/docs/SKILLS.md` when those pipelines are documented.
