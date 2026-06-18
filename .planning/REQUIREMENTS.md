# Requirements: Prices Cascade — Trustworthy Unit Values at Scale

**Defined:** 2026-06-18
**Core Value:** Every processed price item carries a correct pricing basis, a correct COICOP code, and a correct unit value — verifiable against an independently-labeled gold set — so analysts and dashboards consume price data they can trust.

**Acceptance bar:** All three dimensions ≥95% (COICOP measured at 4-digit class). Iteration and per-phase baselines are measured on the 313-row working gold; the final milestone bar is certified on the held-out 187-row set, which is never used during iteration.

## v1 Requirements

### Eval Foundation & Gold Set

- [ ] **FOUND-01**: Eval harness merged from `.claude/worktrees/prices-eval-harness/` into `src/prices/enrich/eval/` and exposed as a first-class `prices eval` CLI command
- [ ] **FOUND-02**: Gold split by provenance at `data/prices/enrich/gold/` into a 313-row WORKING gold (`gold_labels.parquet`, the 13 human-overridden + 300 oracle rows) and a 187-row HELD-OUT certification set (`holdout_cert.parquet`, the cache-verbatim rows quarantined); no working-gold label is accepted verbatim from `cache/enrichments.parquet`
- [ ] **FOUND-03**: The held-out 187 are relabeled by a high-capability LLM oracle (Opus/Sonnet) blind to cache predictions plus human spot-check; the 313 working gold is accepted as-is (already non-cache) with a light spot-check of a random sample plus the 13 overrides
- [ ] **FOUND-04**: `prices eval` reports per-dimension accuracy (pricing_basis, COICOP 4-digit class, unit-value) and per A/B/C bucket against the independent gold
- [ ] **FOUND-05**: Trustworthy baseline accuracy recorded for all three dimensions before any enrich change

### Pricing-Basis Detection

- [ ] **BASIS-01**: `suppress_window` consumer wired into `src/prices/enrich/extract.py` (mechanism is typed in `regex_patterns/types.py` but currently unused)
- [ ] **BASIS-02**: Appliance + apparel suppress patterns added — fixes BUG 3 ("99L Chest Freezer"→volume) and BUG 4 ("T-shirt 5.6oz"→mass); failing tests written first
- [ ] **BASIS-03**: pricing_basis (mass / volume / count) detection ≥95% on the independent gold

### COICOP Classification

- [ ] **COICOP-01**: COICOP 4-digit class accuracy ≥95% on the independent gold
- [ ] **COICOP-02**: 5-digit COICOP subclass code emitted where cascade confidence supports it
- [ ] **COICOP-03**: e5 fine-tune v2 trained (CachedGISTEmbedLoss + hard negatives mined from the KNN index + in-distribution cache positives), deployed only if eval-gated positive
- [ ] **COICOP-04**: KNN thresholds re-calibrated against the independent gold via the A/B eval buckets

### Unit Value

- [ ] **UV-01**: Unit value computed as `listed_price ÷ net_amount ÷ multipack_count` in a canonical basis (per_100g / per_litre / per_unit)
- [ ] **UV-02**: Canonical unit standardization (kg→g, L→ml) applied before unit-value computation
- [ ] **UV-03**: Unit-value correctness ≥95% on the independent gold

### Basket Widening

- [ ] **BASKET-01**: COICOP divisions 02 (alcohol & tobacco), 03 (clothing & footwear), 06 (pharma/health), and electronics added to the basket
- [ ] **BASKET-02**: Per-division KNN pre-seeding (≥150 tier-c-labeled products) completed before tier-b acceptance is enabled for that division
- [ ] **BASKET-03**: `static/channel_coicop_priors.yaml` extended with pharmacy / electronics / clothing channel priors
- [ ] **BASKET-04**: F&B held-out regression eval run after each division addition; <1% F&B accuracy drop gate enforced before proceeding

### Data Source Unification

- [ ] **DATA-01**: Wayback backfill + Common Crawl WARC + fresh collect unified into one deduplicated processed dataset
- [ ] **DATA-02**: Historical labels frozen on observation/input hash — reprocessing never re-labels already-resolved hashes
- [ ] **DATA-03**: Atomic cache-write semantics (sidecar-then-promote) in place before any multi-day reprocess

### Output: Panel & Aggregates

- [ ] **OUT-01**: `build` split into a row-level panel emitter (`build/panel.py`) and a separate aggregation step
- [ ] **OUT-02**: Raw unit-value panel parquet keyed by (country, item, COICOP, period) with provenance fields (observation_hash, source, scrape_date, enrich_tier, model_version, channel, outlier_flag)
- [ ] **OUT-03**: Aggregated series computed via geometric-mean (Jevons), Tukey IQR outlier flagging, and n<10 suppression
- [ ] **OUT-04**: Hardcoded `eap_fnb_*` artifact names replaced by a `basket_id` parameter in `build`
- [ ] **OUT-05**: `publish` renders one dashboard per basket with vendored/inlined Chart.js (no CDN — WB intranet blocks them)
- [ ] **OUT-06**: Basket coverage report (country × COICOP class × period observation counts)

### Throughput / LLM Scaling

- [ ] **PERF-01**: tier-c migrated from deprecated Gemini 2.0 Flash-Lite to Gemini 2.5 Flash-Lite (shutdown 2026-06-01)
- [ ] **PERF-02**: `tenacity`-based retry/backoff replaces the manual rate-limit loop
- [ ] **PERF-03**: tier-c residual fraction shrunk to <20% (measured on a 5% sample) before full-history reprocessing
- [ ] **PERF-04**: Gemini Batch API used for bulk/historical reprocessing

## v2 Requirements

### Confidence & Hierarchy

- **CONF-01**: Per-row calibrated confidence score (Platt scaling / isotonic regression over the independent gold)
- **HIER-01**: Hierarchical COICOP 4-level columns (division/group/class/subclass breakout, not just leaf code)

### Modeling

- **MODEL-01**: Upgrade embedding backend e5-base → `multilingual-e5-large-instruct` (1024-dim, rebuild HNSW indices) — eval-gated

### Aggregation & Distribution

- **AGG-01**: GEKS-Törnqvist aggregation (requires quantity/sales-weight data not in scraped listings)
- **AGG-02**: Channel-stratified aggregated series (once per-country coverage is dense enough to avoid suppression)
- **DIST-01**: Analyst-facing microdata download (requires governance review)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Regions beyond EAP | Milestone scoped to East Asia & Pacific; region widening is a later milestone |
| COICOP transport (07) | Overlaps the existing fuel pipeline; deferred by user |
| Consolidating `src/cpi/coicopping/` duplicate classifier | Separate tech-debt concern, not this milestone |
| Arithmetic-mean aggregation | Anti-feature — biased by outliers; use geometric mean (Jevons) per IMF/ABS |
| Accepting the bootstrapped gold as ground truth | Anti-feature — circular (190/200 from the cache under test) |
| Automatic re-labeling of historical observations | Anti-feature — breaks reproducibility; labels freeze on hash |
| Currency / PPP normalization of unit values | Requires FX-rate infrastructure; future milestone |
| Net-new scrape source onboarding | This milestone unifies existing scrapes, not net-new collection |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 0 | Pending |
| FOUND-02 | Phase 0 | Pending |
| FOUND-03 | Phase 0 | Pending |
| FOUND-04 | Phase 0 | Pending |
| FOUND-05 | Phase 0 | Pending |
| BASIS-01 | Phase 1 | Pending |
| BASIS-02 | Phase 1 | Pending |
| BASIS-03 | Phase 1 | Pending |
| UV-01 | Phase 1 | Pending |
| UV-02 | Phase 1 | Pending |
| UV-03 | Phase 1 | Pending |
| COICOP-01 | Phase 1 | Pending |
| COICOP-02 | Phase 1 | Pending |
| COICOP-03 | Phase 1 | Pending |
| COICOP-04 | Phase 1 | Pending |
| PERF-01 | Phase 1 | Pending |
| PERF-02 | Phase 1 | Pending |
| PERF-03 | Phase 1 | Pending |
| BASKET-01 | Phase 2 | Pending |
| BASKET-02 | Phase 2 | Pending |
| BASKET-03 | Phase 2 | Pending |
| BASKET-04 | Phase 2 | Pending |
| OUT-04 | Phase 2 | Pending |
| DATA-01 | Phase 3 | Pending |
| DATA-02 | Phase 3 | Pending |
| DATA-03 | Phase 3 | Pending |
| OUT-01 | Phase 3 | Pending |
| OUT-02 | Phase 3 | Pending |
| OUT-03 | Phase 3 | Pending |
| OUT-06 | Phase 3 | Pending |
| PERF-04 | Phase 3 | Pending |
| OUT-05 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-18*
*Last updated: 2026-06-18 after initial definition*
