# Prices pipeline — STATUS

Snapshot: **2026-06-11**. This file is a living status doc, not a glossary.
For terminology, see `src/prices/enrich/CONTEXT.md`. For locked architectural
decisions, see `docs/adr/000{1,2,3}-*.md`.

## 1. What this system does

We scrape product listings (name, price, sometimes a category breadcrumb) from
supermarkets, pharmacies, and online aggregators across the EAP region.
Two enrichments turn that raw text into something publishable:

- **Structural fields** — the price's *unit* and *basis*. Is "12 eggs / $5.99"
  a price per piece, per dozen, per kilogram? `pricing_basis`, `standard_unit`,
  `amount_value`, `count`, `multiplier` together encode this.
- **Categorical fields** — what's the product, in UN COICOP terms? `coicop_code`
  is the standard COICOP leaf (e.g. `01.1.1.1` for cereals); `sub_label_id` is
  our finer-grained sub-vocabulary inside that leaf (e.g. `rice`).

A 3-tier cascade does the work — cheap things first, expensive LLM last —
because the raw cache is large and the LLM quota is small.

The eventual output is a country-by-country price panel grouped by COICOP class
and sub-label, designed to feed CPI-style aggregations.

## 2. How the cascade works today

```
product row → tier (a) regex extraction → tier (b) KNN over cluster cache → tier (c) LLM
              (always fires, structural)   (cheap, decides coicop+sub_label)   (LLM-aware reranker, residual only)
```

- **Tier (a) — regex**. `extract.py` pulls pricing_basis / amount_value /
  standard_unit / count / multiplier / promo flags from the product name with
  language-aware regex. Overlay-only — it never decides COICOP. When tier-b
  later accepts with strong cluster agreement (`KNN_CLUSTER_AGREEMENT_MIN`),
  the cluster's `pricing_basis`/`standard_unit` win over tier-a's; per-row
  fields (amount, promos) always overlay.
- **Tier (b) — cluster-resolved KNN**. `index.py` clusters the cache by
  `(canonical_strict, country, channel)` and builds a per-country HNSW index
  over `e5` embeddings of the cluster representatives. Queries embed
  `{breadcrumb} | {item_name}` (ADR-0001, +4.7pp precision, +15.4pp accept).
  Same-channel neighbors are preferred; cross-channel only fires when fewer
  than `MIN_SAME_CHANNEL_KNN=3` same-channel candidates clear the cosine
  threshold (logged as `cross_channel_accept`). Hard accept at
  `cos≥KNN_TAU_HIGH ∧ cluster_agreement_coicop≥KNN_CLUSTER_AGREEMENT_MIN`;
  soft accept on top-K majority + lower cosine.
- **Source-curated short-circuit** (ADR-0002). When a spider's YAML declares
  COICOP codes sharing a single 3-digit class prefix, the cascade writes the
  declared code straight through and skips tier-b/c entirely. Sub_label_id is
  written `null`; tier-a still fires.
- **Tier-c — KNN-aware LLM**. `stages/tier_c.py` calls
  `gemini-3.1-flash-lite` on the residual products, passing the top-K KNN
  neighbors with their resolved `coicop_code + sub_label_id + agreement`. The
  prompt frames the LLM as *auditing* the KNN consensus rather than
  re-solving. Low confidence or unanimous-disagreement escalates to
  `gemini-3-pro`. The UN COICOP `includes`/`excludes` text is now surfaced
  per leaf in the system prompt for disambiguation (2026-06-11). The system
  prompt cache (~170k chars) is server-side cached per Gemini's prompt-cache
  contract.

### Phase 3 — sub_label_id co-gate (new 2026-06-11)

`accept_from_picked` now also computes a *query-time* sub_label agreement:
the fraction of same-coicop top-K neighbors that share the chosen
`sub_label_id`. When that fraction is below `KNN_SUB_LABEL_AGREEMENT_MIN`
(default 0.90), the coicop is accepted but `sub_label_id` is blanked and the
row is logged as `tier_b_knn_partial_sub_label_pending` in `match_log`.

A constrained tier-c entrypoint, `tier_c.enrich_sub_label_only()`, exists for
a future async pass that resolves these partial accepts: it locks the
coicop, restricts the choice to the leaf's valid sub-vocab from
`coicop_subcategories.json`, and reuses `_build_baseline_agent()` so it
inherits the includes/excludes prompt and KNN consensus framing.

### Rate-limit handling (new 2026-06-11)

`prices/enrich/rate_limit.py` adds a proactive per-model RPM/TPM/RPD
token-bucket throttle. `tier_c._run_with_retry_after` acquires a slot before
each LLM call and trues up TPM with the response's actual token usage.
`DailyQuotaExhausted` propagates so the run halts cleanly when RPD is
spent rather than burning retries. RPD state persists across process
restarts in `data/prices/_enrich/_rate_limits.json`. Override the defaults
(free-tier quotas baked into `config.RATE_LIMITS`) via
`src/prices/enrich/static/rate_limits_override.yaml`.

## 3. Where we stand

### 3a. Per-metric

| Metric | Definition | Gate | Current measurement | Status | Known issues |
|---|---|---|---|---|---|
| `pricing_basis` | per-unit, per-weight, per-volume, etc. | non-null ≥95% per source | not yet measured per-source | 🟡 | tier-a coverage spotty for AS-Asian sources |
| `standard_unit` | base unit (`g`, `ml`, `item`) | structural-precision ≥98% | not yet measured | 🟡 | depends on pricing_basis upstream |
| `amount_value` | numeric quantity in `standard_unit` | structural-precision ≥98% | not yet measured | 🟡 | depends on pricing_basis upstream |
| `count` | piece count for multi-packs | overlay-only, no gate | always overlaid from tier-a | 🟢 | — |
| `multiplier` | inner pack count | overlay-only, no gate | always overlaid from tier-a | 🟢 | — |
| `is_promotion`/`is_bundle`/`is_multipack` | promo flags | overlay-only | always overlaid from tier-a | 🟢 | — |
| `coicop_code` | UN COICOP 4-digit leaf | cell gate: ≥2 sources + ≥50 rows + `cluster_agreement_coicop≥0.85` on ≥50% rows | 87 (country × 3-digit) cells pass globally; Japan leads with 19 | 🟡 | taiwan_china at 0 cells — only 1 channel slug (`hypermarket`), gate's 2-source proxy mis-fits |
| `sub_label_id` | atom inside a COICOP leaf | per-cell gate active only on **rich** leaves (≥2 real sub-labels) | 87 of 538 leaves (16.2%) are rich; 86.2% of cache rows land in non-rich leaves so the gate is a no-op for most data | 🔴 | sub-vocab undercurated — see §4 |
| `unit_value` | derived: amount × count × multiplier ÷ pricing_basis | downstream of pricing_basis + standard_unit + amount_value | not yet computed | 🟡 | needs build stage |

### 3b. Per-country publishability

13 onboarded EAP countries, all "data-collecting" except new_zealand
(below `KNN_BOOTSTRAP_CLUSTER_FLOOR=150`). "Publishable cells" = (country ×
COICOP 3-digit) cells passing the locked COICOP gate.

| Country | Clusters | Cells passing COICOP gate | Data-collecting? | Notes |
|---|---:|---:|---|---|
| taiwan_china | 9 851 | 0 | ✅ | 1 channel only — fails 2-source proxy. Pubishability blocked on source diversity, not data volume. |
| japan | 3 364 | 19 | ✅ | Leads the region for publishable cells. |
| cambodia | 1 715 | 10 | ✅ | Strong COICOP coverage across hypermarket + aggregator. |
| philippines | 1 524 | 2 | ✅ | More cells should pass — investigate channel-count proxy. |
| vietnam | 776 | 1 | ✅ | |
| malaysia | 481 | 1 | ✅ | |
| indonesia | 423 | 3 | ✅ | |
| myanmar | 385 | 0 | ✅ | |
| australia | 358 | 0 | ✅ | |
| thailand | 354 | 0 | ✅ | |
| fiji | 343 | 0 | ✅ | |
| singapore | 294 | 1 | ✅ | |
| new_zealand | 177 | 1 | ⚠️ | Below bootstrap floor — cluster index not built. |

### 3c. Taxonomy state — drives sub_label_id quality

- 538 deepest-available COICOP leaves total.
- 87 (16.2%) have a curated sub-vocabulary with ≥2 real entries — the *rich* leaves.
- 95 (17.7%) are UN-designated residuals (`Other`, `n.e.c.` titles) — by-design catch-all, no curation needed.
- **356 (66.2%) are placeholder-only non-residuals — genuine curation gaps.**

Of those 356 gaps, the 8 highest-cache-volume leaves account for the bulk
of authorable headroom: `06.1.1.1` (medicines), `05.4.0.3` (kitchen
utensils), `05.6.1.1` (cleaning), `13.2.1.1` (jewellery), `09.7.1.1`
(textbooks), `09.7.4.0` (stationery), `09.2.1.2` (toys, non-residual
portion), `09.3.2.2` (pet products).

### 3d. Cache cluster cache is effectively singletons

Phase 0 audit (2026-06-11) found `cluster_size ≈ 1.00` everywhere
(20 045 clusters / 20 060 rows). The within-cluster
`cluster_agreement_sub_label` stored in the cluster parquet is therefore
trivially 1.0 for all rich leaves. The Phase 3 gate works on **query-time**
neighbor agreement instead — measured at lookup, not stored. This means
`KNN_SUB_LABEL_AGREEMENT_MIN=0.90` is an initial conservative guess; tune
from `match_log.parquet` after the next collection run.

### 3e. Quota state (as of 2026-06-11 user screenshot)

| Model | RPM | TPM | RPD |
|---|---:|---:|---:|
| gemini-3.1-flash-lite | 23 / 15 (🔴 over) | 463 K / 250 K (🔴 over) | 174 / 500 |
| gemini-embedding-001 | 100 / 100 (at limit) | 3.6 K / 30 K | 6 / 1000 |

The new rate-limit throttle (§2) keeps the workload under these ceilings
proactively on the next run, and halts on RPD instead of burning retries.

Phase 1 eyeball tests + Phase 2 proposals (8 sub-vocabs + 3 eyeball
classifications + 1 v1 discard = 12 flash-lite calls total) ran on this
day and stayed inside the throttle's 13-RPM ceiling without breaching
quota.

## 4. What's next

In rough priority order — sub_label_id quality is the lowest-status metric,
so the first three items target it.

1. **Sub-vocab authoring — MERGED.** All 8 v2 proposals merged into
   `src/prices/enrich/static/coicop_subcategories.json` on 2026-06-11.
   Per-leaf counts (incl. auto `_other`): 06.1.1.1 → 9, 05.4.0.3 → 10,
   05.6.1.1 → 10, 13.2.1.1 → 7, 09.7.1.1 → 8, 09.7.4.0 → 9,
   09.2.1.2 → 10, 09.3.2.2 → 9. Rich-leaf count jumped 87 → 95; prompt
   size grew 170 874 → 176 955 chars. The v1 prompt overfit to noisy
   scraped examples (proposed protein supplements for the medicines
   leaf because the cache had mislabeled food rows under 06.1.1.1); the
   v2 prompt makes the UN definitional text authoritative and surfaces
   rejected examples in `rationale`. Coverage gaps to consider for a
   future pass: 06.1.1.1 lacks antibiotics/antihistamines/antacids;
   05.4.0.3 lacks knives + kitchen tools; 05.6.1.1 lacks
   toilet/bathroom/air-freshener; 13.2.1.1 lacks gemstone-only entries;
   09.3.2.2 lacks fish/bird/litter. Re-author via
   `python scripts/prices_phase2_propose_subvocab.py run --codes <code> --suffix .vN`.
2. **Phase 1 eyeball tests — VERIFIED**. 3 cases ran against live tier-c
   (`data/prices/_enrich/_audit/phase1_eyeball/`): Coca-Cola → `01.2.6.0.0`
   (soft drinks in COICOP 2018 sit under 01.2.6 inside Food &
   non-alcoholic beverages — my test expectation was wrong on this);
   Vitamin C 500mg → `06.1.1.1` (medicines, steered away from food +
   personal care); Apple Watch → `08.1.9.1` (exactly the code the
   13.2.1.1 excludes text cross-references for smartwatches). The
   includes/excludes block is real-world effective.
3. **Threshold tuning for `KNN_SUB_LABEL_AGREEMENT_MIN`**: after the next
   collection run, histogram `sub_label_query_agreement` from
   `match_log.parquet` on partial-accept rows and re-tune away from the 0.90
   conservative default.
4. **Source-count proxy fix**: the current 2-source gate counts distinct
   channels per country × COICOP 3-digit cell. taiwan_china has 9 851
   clusters and 0 passing cells because every source is tagged
   `channel=hypermarket`. Either thread source slug through cluster parquet
   or relax the proxy to "≥2 sources within channel" using the
   `clusters_<country>.parquet` source counts.
5. **Async sub_label resolve pass** that consumes
   `tier_b_knn_partial_sub_label_pending` rows from `match_log.parquet`
   and resolves them via `tier_c.enrich_sub_label_only()` when quota is
   healthy. Currently the partial-accept rows just ship with
   `sub_label_id = null`.
6. **Split oversized modules** — `tier_c.py` 637 LoC, `index.py` 523 LoC,
   `enrich.py` 544 LoC. The 500-LoC cap is being violated.
7. **`build` and `publish` stages** — still stubs; needed before any data
   ships externally.

### Deferred (north-star, do-not-touch-yet)

- Distillation pipeline (a small student model that mimics tier-c+b).
  Unlock at ≥50k tier-c-resolved cache rows.
- Embedding backend flip (`e5` → `gemini-embedding-001`). Wired but skipped
  — current quota constraints would make this immediately rate-limited.
- voyage-3 / BGE-M3 bake-off.
- Pacific Islands single-source carve-out — explicitly rejected
  (2-source rule applies globally).

## 5. What we don't know yet

- True per-source `pricing_basis` precision. We don't have a per-source
  eval set; the 95% gate is unmeasured.
- `unit_value` accuracy — `build` stage that derives it doesn't exist yet.
- Query-time `cluster_agreement_sub_label` distribution. The audit relied
  on within-cluster values which are trivially saturated at 1.0; we need
  to log the live KNN-time values to honestly tune the new gate.
- Whether the new includes/excludes prompt block actually changes
  ambiguous calls in production (Phase 1 eyeball tests deferred).
- Cost-per-row for tier-c. `cost.json` / similar telemetry doesn't exist.
