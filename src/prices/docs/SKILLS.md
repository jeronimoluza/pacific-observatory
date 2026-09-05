# Prices — Skills

The `.claude/skills/` entries that operate on the prices pipeline. Skills
auto-surface as agent capabilities, so a stale one is a live drift risk. See
`GLOSSARY.md → Retired — do not use` for the term-by-term mapping.

## Current — safe to run

| Skill | What it does |
|---|---|
| `onboard-price-sources` | Depth-audit existing coverage, then discover, scaffold, and end-to-end-test new price sources (platform/marketplace-first discovery → probing → spider/fetcher + YAML under `src/prices/configs/` → automated test → coverage report). Scopes to one country, a region, a commodity gap, or a single URL. Renamed from `onboard-country-price-sources` 2026-08-04 — discovery is not a per-country activity. |

`onboard-price-sources` is the only prices skill. The KNN/HNSW cascade skills
(`classify-base-item-prices`, `diagnose-prices-cascade`, `improve-prices-cascade`,
`resolve-price-conflicts`, `iterate-retailer-unit-values`,
`spike-findings-template-repo`) were removed during the 2026-09-05 consolidation
onto `main`. They narrated tier-a/tier-b/tier-c, `base_items` / `gazetteer` /
CANDIDATE→GREEN, W5 consensus/witness, and CLI verbs that do not exist
(`prices classify`, `prices iterate`, `prices classify-corpus`). The live classify
path is only `extract()` + `(embedding → head)` + vetoes; `base_item` appears
**0×** in `src/`. This closes item #2 of
`sessions/2026-07-27-docs-consolidation.md`.

## Not prices

`assess-newspaper-source`, `onboard-region-newspapers`, `refresh-text-region`,
`text-storage`, `translate-english-keywords` belong to **text**;
`update-fuel-crisis-policy` and `update-food-security-policy` belong to **fuel**
and **policy** respectively. They get their own `src/<pipeline>/docs/SKILLS.md`
when those pipelines are documented.
