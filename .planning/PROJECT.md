# Prices Cascade — Trustworthy Unit Values at Scale

## What This Is

The `prices` pipeline of the Pacific Observatory turns scraped retail product listings into structured price observations: it detects each item's pricing basis (mass / volume / count), classifies it to a COICOP 2018 category, and computes a normalized unit value. This milestone re-baselines that enrich cascade on a *trustworthy* gold set, widens it beyond the current food-&-beverage proof-of-concept into more COICOP divisions, and unifies all historical and fresh scrapes into one processed dataset — producing a raw unit-value panel for downstream analysts and aggregated series for dashboards.

## Core Value

Every processed price item carries a **correct pricing basis, a correct COICOP code, and a correct unit value** — verifiable against an independently-labeled gold set — so analysts and dashboards consume price data they can trust.

## Requirements

### Validated

<!-- Inferred from existing code (brownfield). These already ship and are relied upon. -->

- ✓ Tier-a regex structural extraction overlays pricing_basis / amount / count / multipack / promos — existing
- ✓ Tier-b KNN matching over per-country cluster-resolved cache (HNSW indices, e5 embeddings) — existing
- ✓ Tier-c KNN-aware LLM reranker (Gemini via pydantic-ai) for residual COICOP classification — existing
- ✓ Unified collection: Scrapy spiders + per-source fetchers (`prices collect`) — existing
- ✓ Resumable Wayback backfill (`prices backfill`) and Common Crawl WARC ingest (`prices common-crawl`) — existing
- ✓ `build` / `publish` assemble + render the EAP food-&-beverage PoC basket — existing
- ✓ Eval harness with a gold-label apparatus (gold v2 → v3 lineage, A/B/C buckets) — existing (lives in a worktree, not yet merged into `src/`)

### Active

<!-- This milestone. Hypotheses until shipped and validated. -->

- [ ] Re-establish a **trustworthy, independently-labeled 500-row gold set** at the canonical path `data/prices/enrich/gold/` — NOT bootstrapped from the distrusted `cache/enrichments.parquet`
- [ ] Re-baseline cascade accuracy against the trustworthy gold across all three dimensions (pricing_basis, COICOP, unit value); treat existing `enrichments.parquet` / `cache.parquet` as unverified
- [ ] Drive **pricing-basis detection (mass / volume / count)** toward ~100% on gold — including fixing the appliance/apparel false-extraction bugs (BUG 3 "99L Chest Freezer"→volume, BUG 4 "T-shirt 5.6oz"→mass)
- [ ] Drive **COICOP classification** toward ~100% on gold
- [ ] Compute **correct unit values** (price ÷ normalized amount × count/multipack) for every processed item
- [ ] **Widen the basket** beyond food & beverage into COICOP 02 (alcohol & tobacco), 03 (clothing & footwear), pharma (06 health), and electronics
- [ ] **Unify all data sources** — Wayback backfill + Common Crawl WARC + fresh collect — into one processed dataset
- [ ] **Shrink tier-c reliance** (stronger tier-a regex + tier-b KNN + e5 fine-tune) AND **scale the LLM tier** (throughput/quota/batching) for the residual
- [ ] Produce a **raw unit-value panel** (per country / item / COICOP, over time) for analysts AND **aggregated series** for dashboards

### Out of Scope

- Regions beyond EAP — milestone is scoped to East Asia & Pacific; widening regions is a later milestone
- COICOP transport (07) — offered but deferred; overlaps the existing fuel pipeline and not prioritized for v1
- Consolidating the duplicate COICOP classifier in `src/cpi/coicopping/` — separate tech-debt concern, not this milestone
- The fuel pipeline and legacy fuel dashboards — unrelated pipeline
- Onboarding entirely new scrape sources — this milestone unifies *existing* scrapes, not net-new collection

## Context

- **Brownfield.** Full codebase map exists at `.planning/codebase/` (ARCHITECTURE, STACK, CONCERNS, CONVENTIONS, INTEGRATIONS, STRUCTURE, TESTING — analyzed 2026-06-17).
- **Cascade architecture** (`src/prices/enrich/`): 3-tier cascade over deduped products. Tier-a regex; tier-b KNN with `cluster_key = (canonical_strict, country, channel)`; tier-c LLM reranker. Tier-b accepts guarded by `KNN_CLUSTER_AGREEMENT_MIN` (0.90) + pricing_basis agreement; same-channel KNN preferred (`MIN_SAME_CHANNEL_KNN=3`).
- **Gold-set discovery (2026-06-18):** A 500-row gold set already exists at `data/prices/_enrich/gold_labels.parquet` (cols `basis_gold`, `val_gold`, `unit_gold`, `cnt_gold`, `mult_gold`, `coicop_code_gold`, `sub_label_gold` + country/source/language/modality/product_name). **But** its manifest shows it was sampled from `cache/enrichments.parquet` with 190/200 cache predictions accepted unchanged and machine-labeled (`labeler_model`) — so it inherits the cache's errors and cannot certify the cache is fixed. Hence the first Active requirement.
- **Known cascade concerns** (from `.planning/codebase/CONCERNS.md`): tier-a appliance/apparel false unit extraction; KNN thresholds are hand-tuned single-knob levers (use the eval A/B buckets before changing); Gemini rate limits cap tier-c throughput (~41% of rows reach tier-c); build/publish hard-code `eap_fnb_*` names.
- **Prior experiments** (project memory): paired-cleaning embedding was net-negative; hierarchical COICOP-prefix tier-b gives correct coarse labels to residuals; e5 anchors-only fine-tune v1 confirms the "shrink tier-c" lever (+3.4 leaf, errors halved, no forgetting).

## Constraints

- **Tech stack**: Python 3.11+; existing cascade (regex + e5/sentence-transformers + hnswlib KNN + Gemini/pydantic-ai). Ruff line-length 100; **500-line max per Python file** (split before adding). UTC timestamps only.
- **Data safety**: Never delete or modify files under `data/` or `outputs/` — user handles all destructive actions manually. Never commit `data/`, `outputs/`, or `openspec/`.
- **Performance**: Gemini rate limits (~15 RPM / 250k TPM / 500 RPD) gate tier-c throughput — the central bottleneck that widening the basket + unifying all history will stress.
- **Ground truth**: Accuracy must be measured against the *independent* gold set, not `enrichments.parquet` / `cache.parquet`.
- **Eval harness location**: the eval module currently lives only in `.claude/worktrees/prices-eval-harness/`, not merged into `src/prices/enrich/eval/` — may need merging first.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Widen the basket (not just harden F&B) | User wants coverage beyond the PoC: COICOP 02, 03, pharma, electronics | — Pending |
| Measure ~100% against an independent 500-row gold set; assume `cache`/`enrichments` parquets are wrong | The existing gold was bootstrapped from the distrusted cache (190/200 unchanged) | — Pending |
| Both shrink AND scale the LLM tier | Tier-c is the throughput bottleneck; widening + full history multiplies its load | — Pending |
| Output both a raw unit-value panel and aggregated series | Analysts need row-level data; dashboards need aggregates | — Pending |
| Divisions for v1: COICOP 02, 03, 06 (pharma), electronics; defer transport (07) | User selection; transport overlaps fuel pipeline | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-18 after initialization*
