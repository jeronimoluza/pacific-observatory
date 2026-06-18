# Roadmap: Prices Cascade — Trustworthy Unit Values at Scale

## Overview

Five phases turn a circularly-contaminated PoC cascade into a verified, widened, and unified price-observation pipeline. Phase 0 establishes the only ground truth that can certify improvements. Phase 1 hardens tier-a/b accuracy and shrinks LLM reliance before anything else changes at scale. Phase 2 widens the basket with guards against cold-start misclassification. Phase 3 unifies all historical data in one atomic pass. Phase 4 generalises build and publish so every basket gets its own dashboard without code duplication.

## Phases

- [ ] **Phase 0: Eval Foundation & Independent Gold Set** - Merge the eval harness; split the gold by provenance into a 313-row working set + a 187-row held-out cert set (relabeled blind to cache); record trustworthy baseline accuracy
- [x] **Phase 0.5: Cascade Cleanup (behavior-preserving)** - Kill dead paths/unused features, split file sprawl (10k-line c01_subs.py), consolidate scattered knobs, untangle the _sub_labels.parquet ↔ c*_subs.py source-of-truth knot — all gated by identical `prices eval` numbers before/after (completed 2026-06-18)
- [ ] **Phase 1: Tier-a/b Hardening on Existing F&B Basket** - Wire suppress_window, fix BUG 3/4, deploy IMF unit-value formula, migrate to Gemini 2.5, re-calibrate KNN; shrink tier-c to <20%
- [ ] **Phase 2: Basket Widening (COICOP 02/03/06/electronics)** - Pre-seed KNN per division, extend priors, parameterise basket_id; enforce <1% F&B regression gate
- [ ] **Phase 3: Full-History Unification + Panel Emit** - Unify all three ingestion paths; atomic cache writes; emit row-level unit-value panel + Jevons aggregates
- [ ] **Phase 4: Publish Generalisation + Dashboards** - One vendored-Chart.js dashboard per basket; basket_id-parameterised publish pipeline

## Phase Details

### Phase 0: Eval Foundation & Independent Gold Set

**Goal**: A working `prices eval` CLI command and a provenance-split gold (313-row working set + 187-row held-out cert set relabeled blind to cache) record the first trustworthy baseline — so every downstream change can be measured against ground truth, not circular cache predictions.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05
**Success Criteria** (what must be TRUE):

  1. `prices eval` runs end-to-end from the main branch (`src/prices/enrich/eval/`) and reports per-dimension accuracy on a gold parquet
  2. The 500-row gold is split by provenance: the 187 cache-verbatim rows (`source_set=v3` with empty `labeler_notes`, accepted unchanged from cache) are removed, leaving a 313-row WORKING gold at `data/prices/enrich/gold/gold_labels.parquet` (300 oracle + 13 human-overridden) with no rows accepted verbatim from the production cache; a light spot-check (random sample + the 13 human overrides) confirms labels match raw product names
  3. The 187 quarantined rows form a HELD-OUT certification set at `data/prices/enrich/gold/holdout_cert.parquet`: their cache-derived labels are stripped and re-labeled blind to cache by an LLM oracle (Opus/Sonnet) plus human spot-check; this set is never used during Phase 1–3 iteration and is reserved to certify the final ≥95% milestone bar
  4. `prices eval` reports baseline accuracy across all three dimensions (pricing_basis, COICOP 4-digit class, unit-value) broken down by A/B/C bucket on the 313-row working gold, before any enrich code changes
  5. Baseline numbers are recorded on disk under `.planning/` as a durable reference artifact (e.g. `BASELINE.md`, capturing run conditions + commit SHA); they differ from the inflated scores the contaminated v2 gold would have produced. (Note: `.planning/` is gitignored in this repo, so "recorded on disk" — not a git commit — is the bar.)

**Plans**: 2/3 plans executed

- [x] 00-01-PLAN.md — Merge eval harness into src/prices/enrich/eval/, wire `prices eval` CLI, repoint GOLD_PATH (FOUND-01)
- [x] 00-02-PLAN.md — Provenance split (313 working + 187 raw holdout, additive), run eval, record committed baseline, recalibrate CI floors (FOUND-02/04/05)
- [ ] 00-03-PLAN.md — Blind-to-cache oracle relabel of the 187 held-out set → holdout_cert.parquet + human spot-check (FOUND-02/03)

### Phase 0.5: Cascade Cleanup (behavior-preserving)

**Goal**: The `src/prices/enrich/` cascade is legible and lands clean for Phase 1 — dead paths and unused features removed, file sprawl split, knobs consolidated to one tuning surface, and the sub-label storage knot untangled — with **zero** change to cascade outputs, proven by identical `prices eval` numbers before and after.
**Mode:** mvp
**Depends on**: Phase 0 (needs the 313-row working-gold baseline as the before/after comparison point)
**Requirements**: TBD (see `.planning/notes/cascade-cleanup-scope.md`)
**Success Criteria** (what must be TRUE):

  1. An inventory doc maps dead paths, unused features, scattered knobs, and the full `_sub_labels.parquet` dependency graph before any deletion (read-only discovery pass complete)
  2. `prices eval` on the 313-row working gold produces **identical** accuracy across all three dimensions (pricing_basis, COICOP 4-digit, unit-value) before and after the cleanup — no behavior change
  3. No single Python file in `enrich/` exceeds the 500-line repo limit after the split (10k-line `c01_subs.py` and siblings broken up with imports preserved), with **two recorded exceptions deferred to Phase 1**: `stages/tier_c.py` (769) and `stages/enrich.py` (638) — orchestration code Phase 1 rewrites when hardening the cascade, so splitting them now then rewriting there is double-churn. The SC3 gate at execution is scoped to phase-touched files (the migrated `keywords/coicop/` modules, `index.py`, the new `tier_b/` package) and whitelist-diffs out those two `stages/` files. The `c01.py`/`c05.py`/`c09.py` CLASS modules ARE in scope — they dissolve via the same D-01/D-02 data migration as the `c{NN}_subs.py` sub-labels (both are auto-generated from `coicop_categories.xlsx`), not a separate split.
  4. Cascade thresholds/tunables (`KNN_BOOTSTRAP_CLUSTER_FLOOR`, `KNN_CLUSTER_AGREEMENT_MIN`, `KNN_SUB_LABEL_AGREEMENT_MIN`, `MIN_SAME_CHANNEL_KNN`, channel priors path) are readable from one tuning surface with values unchanged
  5. The `_sub_labels.parquet` ↔ `c*_subs.py` source-of-truth knot is resolved per the design decision in `.planning/research/questions.md` (Q1), content-preserving and verified by eval parity
  6. Dead paths and unused features identified in the inventory are removed (only entries with no live callers); no orphaned imports remain
  7. The tier-a `regex_patterns/` routing/order knot is single-sourced: a `kind` field on `PackPattern` makes bucket-routing explicit and the five hand-maintained ID-order tuples in `dict_view.py` collapse to one `MODULE_ORDER`; the `any/` mislabel is fixed (→ `shared/`) and the existing `_cjk_shared/` is generalized to a `script/<family>/` axis with a `_SCRIPT_OF` lang→script table (CJK+Latin only — new scripts deferred to seed `regex-script-families`). Guarded by a byte-identity snapshot test + a no-silent-drop test, and verified by eval parity (SC2). See `.planning/notes/tier-a-regex-reorg.md`
  8. The tier-b (KNN) layer is reorganized: loose root modules (`index`, `embed`, `cache`, `cross_check`, `brand_prior`, `propagation`, `narrowness`, `pool_filter`, `taxonomy_index`) are consolidated into a `tier_b/` package mirroring `stages/`/`keywords/`/`regex_patterns/` (imports preserved, no orphans); and index provenance moves off folder-names — `reindex_all()` writes a fat `meta.json` (`model_path`, `embed_dim`, `backend`, `knn_score_hard_min`, `n_clusters`, `built_at`, `git_sha`) plus a dir-level `manifest.json`, so a base index and a fine-tuned index are distinguishable from metadata alone (today both read `{"backend":"e5","dim":768}`). Additive metadata only — acceptance code reads the same fields, verified by eval parity (SC2). On-disk layout restructure + variant lifecycle/cleanup deferred to seed `tier-b-index-layout-and-lifecycle`. See `.planning/notes/tier-b-file-reorg.md`

**Scope boundary**: behavior-preserving only — no content/label fixes, no threshold retuning. Those belong to Phase 1+.

**Plans**: 6/6 plans complete

- [x] 00.5-01-PLAN.md — Read-only inventory (SC1) + prices eval parity anchor (D-09) [Wave 1]
- [x] 00.5-02-PLAN.md — Resolve source-of-truth knot: data-store-as-truth, collapse BOTH c{NN}.py CLASS trees + c{NN}_subs.py sub-label sprawl (SC5/SC3) [Wave 2]
- [x] 00.5-03-PLAN.md — Consolidate KNN knobs into one YAML tuning surface, values unchanged (SC4) [Wave 2]
- [x] 00.5-04-PLAN.md — Tier-a regex single-source: kind + MODULE_ORDER + shared/script axis (SC7) [Wave 3]
- [x] 00.5-05-PLAN.md — Tier-b package + fat meta.json/manifest.json provenance, split index.py (SC8/SC3) [Wave 3]
- [x] 00.5-06-PLAN.md — Coverage-aware dead-code removal with approve-once gate (SC6) [Wave 4]

### Phase 1: Tier-a/b Hardening on Existing F&B Basket

**Goal**: The cascade produces correct pricing_basis, COICOP, and unit-value on the independent gold at >=95% across all three dimensions, and tier-c handles <20% of a 5%-sample corpus — making full-history reprocessing tractable within the Gemini RPD budget.
**Mode:** mvp
**Depends on**: Phase 0.5
**Requirements**: BASIS-01, BASIS-02, BASIS-03, UV-01, UV-02, UV-03, COICOP-01, COICOP-02, COICOP-03, COICOP-04, PERF-01, PERF-02, PERF-03
**Success Criteria** (what must be TRUE):

  1. `extract("99L Chest Freezer", ...)` returns `pricing_basis=count`; `extract("T-shirt 5.6oz", ...)` returns `pricing_basis=count` (BUG 3 and BUG 4 fixed, tests written first and passing)
  2. `prices eval` on the independent gold reports pricing_basis >=95% and COICOP 4-digit class >=95%
  3. Unit value computed as `listed_price / net_amount / multipack_count` in canonical basis (per_100g / per_litre / per_unit) with kg→g and L→ml standardisation; unit-value correctness >=95% on independent gold
  4. `prices process` uses Gemini 2.5 Flash-Lite (not deprecated 2.0 Flash-Lite) with tenacity retry/backoff replacing the manual rate-limit loop
  5. Tier-c fraction measured on a stratified 5% corpus sample and confirmed <20%; the sample measurement is recorded before any full-history run is attempted

**Plans**: TBD

### Phase 2: Basket Widening (COICOP 02/03/06/electronics)

**Goal**: COICOP divisions 02, 03, 06, and electronics are live in the basket with per-division KNN pre-seeding and channel priors in place, F&B accuracy has not regressed >1%, and `build` no longer hard-codes `eap_fnb_*` artifact names.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: BASKET-01, BASKET-02, BASKET-03, BASKET-04, OUT-04
**Success Criteria** (what must be TRUE):

  1. `prices process` successfully classifies products from at least one pharmacy, one clothing/footwear, one alcohol/tobacco, and one electronics source into their respective COICOP divisions
  2. Each new division's KNN index has >=150 pre-seeded tier-c-labeled products before tier-b acceptance is enabled for that division (bootstrap floor met)
  3. `static/channel_coicop_priors.yaml` contains priors for pharmacy, electronics, and clothing channel types
  4. F&B held-out eval run after each division addition confirms <1% regression in F&B accuracy before proceeding to the next division
  5. `prices build --basket-id <name>` works and produces `{basket_id}_observations.parquet`; the string `eap_fnb_observations` does not appear as a hardcoded path in build or publish source

**Plans**: TBD

### Phase 3: Full-History Unification + Panel Emit

**Goal**: All three ingestion paths (Scrapy fresh, Wayback backfill, Common Crawl WARC) flow into one deduplicated processed dataset; the cache is written atomically; and the pipeline emits a row-level unit-value panel parquet plus Jevons-aggregated series with Tukey outlier flagging and n<10 suppression.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03, OUT-01, OUT-02, OUT-03, OUT-06, PERF-04
**Success Criteria** (what must be TRUE):

  1. `prices process` consumes raw artifacts from all three ingestion paths and the cache contains no duplicate `input_hash` rows; per-source observation counts visible in `prices status`
  2. Historical labels do not change on reprocess: running `prices process` twice on the same corpus produces bit-identical cache output (freeze-on-accept; no re-labeling of resolved hashes)
  3. A failed or interrupted reprocess does not corrupt `enrichments.parquet` — the sidecar-then-promote pattern is in use and a `_run_complete` sentinel controls promotion
  4. `build/panel.py` emits `{basket_id}_unit_value_panel.parquet` partitioned by country with provenance fields (observation_hash, source, scrape_date, enrich_tier, model_version, channel, outlier_flag)
  5. Aggregated series use geometric mean (Jevons), Tukey IQR outlier flagging, and n<10 suppression flag; basket coverage report (country x COICOP class x period counts) is emitted alongside the panel
  6. Post-run `prices eval` on the independent gold confirms no label drift vs. Phase 1 baseline; Gemini Batch API used for historical tier-c calls

**Plans**: TBD

### Phase 4: Publish Generalisation + Dashboards

**Goal**: `prices publish` renders one standalone HTML dashboard per basket using vendored/inlined Chart.js, with no CDN dependencies, and the full end-to-end pipeline from `prices build` to a browser-viewable dashboard works for every basket added in Phase 2.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: OUT-05
**Success Criteria** (what must be TRUE):

  1. `prices publish --basket-id <name>` renders `outputs/prices/{basket_id}_dashboard.html` for each of the baskets from Phase 2 (fnb, alcohol_tobacco, clothing, pharma, electronics)
  2. Each dashboard loads correctly in a browser with no network requests to CDN hosts (Chart.js and noUiSlider fully vendored/inlined); verified on the WB intranet profile (no external JS sources)
  3. The publish module contains no hardcoded `eap_fnb` strings; artifact paths are derived entirely from `basket_id`

**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Eval Foundation & Independent Gold Set | 2/3 | In Progress|  |
| 0.5. Cascade Cleanup (behavior-preserving) | 6/6 | Complete   | 2026-06-18 |
| 1. Tier-a/b Hardening on Existing F&B Basket | 0/TBD | Not started | - |
| 2. Basket Widening (COICOP 02/03/06/electronics) | 0/TBD | Not started | - |
| 3. Full-History Unification + Panel Emit | 0/TBD | Not started | - |
| 4. Publish Generalisation + Dashboards | 0/TBD | Not started | - |
