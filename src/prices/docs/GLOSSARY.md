# Prices — Glossary

The controlled vocabulary for the prices pipeline. If a term is defined here,
use it exactly; if a term is in the **Retired** table, do not use it — grep the
replacement instead. This file is the single arbiter when a name is ambiguous.

Scope note: this glossary is prices-specific. Project-wide terms (Region,
Subregion, Country slug, Effective language) live in `CLAUDE.md`.

Last reconciled against code: 2026-07-27 (see
`sessions/2026-07-27-docs-consolidation.md` for the audit that produced it).

---

## Current terms (live)

- **tier-a / structural extraction** — the deterministic regex enricher
  (`enrich/extract.py` + `enrich/regex_patterns/`). Overlays quantity fields
  (`pricing_basis`, `amount_value`, `standard_unit`, `count`, `multiplier`,
  promo flags) onto each product name. **Never** decides COICOP. The only
  surviving "tier" term.
- **(embedding → head) classifier** — the live COICOP classifier. Canonical
  name for the leaf predictor: a frozen Qwen3-Embedding ensemble → a
  logistic-regression head. Do not call it "the model" or "tier-b".
- **ensemble embedder** — concatenation of three frozen Qwen3-Embedding encoders
  (0.6B + 4B + 8B) → 7680-d, each block L2-normalized independently, **no global
  renorm** (`enrich/embedding.py`). Block order is load-bearing.
- **tau (τ)** — the single **global** accept threshold, derived out-of-fold at
  the target precision (cov@98) in `enrich/classifier/train.py`. Not per-leaf.
- **veto — REJECT / REROUTE** — per-leaf trap lexicon applied to accepted
  predictions (`enrich/vetoes.py`, `veto_lexicon.parquet`). REJECT withholds a
  prediction; REROUTE rewrites the leaf and is held to a higher precision bar.
- **Layer-1 basis audit** — rejects/flags physically-impossible
  `(coicop_leaf, pricing_basis)` pairs (`enrich/audit.py`,
  `basis_denylist.parquet`). Precision-first: quarantine, never fabricate.
- **Layer-2 unit-value audit** — statistical outlier flagging per
  `(coicop_code, country)` cell in log space, robust `median ± 3·MAD`
  (`build/unit_value_audit.py`). Abstains on thin cells; never rejects.
- **trust_level / trust_uv** — the Layer-1 / Layer-2 grades. The consumable
  deliverable is rows where **both are `"high"`**.
- **narrow source** — a source whose declared `coicop_codes` share one 3-digit
  prefix; its rows short-circuit the classifier to the declared code
  (`state="narrow_source"`).
- **input_hash** — the pure structural dedup/join key (`enrich/versioning.py`).
  `prepare` dedups to one row per `input_hash`; `classify` inherits it unchanged;
  `build` joins the classified cache to the price side on it.
- **products_input.parquet** — dedup identity table (one row / `input_hash`), the
  classify input, under `data/prices/enrich/`.
- **classified.parquet** — the classify output cache, keyed by `input_hash`,
  under `data/prices/enrich/cache/`. (Replaced the retired `enrichments.parquet`.)
- **gold (v5)** — the `_load_gold()` union of `gold_v5_*` parquets under
  `data/prices/enrich/gold/` (~14.4k rows). Trains **and** evaluates the head.
- **gold-labeling consensus** — two-labeler agreement (codex + gemini) in the
  gold-growth loop (`prices label`). Distinct from the retired cascade
  "consensus" — this sense is **live**.
- **channel** — per-source outlet type. Enforced by the `Channel` Literal in
  `enrich/schemas.py` (Pydantic-validated at load via `config.py`), defined by
  the table below. Every value is defined by its **discriminating test** — how
  to tell it from its nearest neighbour — because `aggregator` failed by being
  defined by what an outlet is *called* rather than by a decision it drives.
  A source whose measured division profile contradicts its tag is a **flag for
  review, not an automatic reclassification**: the taxonomy asserts, the
  measurement audits.

<!-- channel-values:start -->

| Value | Discriminating test | Examples |
|---|---|---|
| `supermarket` | General grocery chain, first-party inventory | `coles_au`, `emart_kr`, `fairprice` |
| `hypermarket` | Big-box genuinely cross-selling food **and** general merchandise | `aeon_online`, `carrefour_tw`, `hypermart` |
| `convenience` | Small-format chain, limited SKU count | `alfagift` |
| `fresh-market` | Fresh produce / butcher / seafood, little packaged goods | `pasar_tani`, `rautuoi247`, `sayur` |
| `specialty-food` | Narrow food/drink range — wine, coffee, imports, organic | `cellarmaster_hk`, `horizon_farms` |
| `marketplace` | **Third-party sellers**, long-tail catalog, seller-authored names | `rakuten`, `yahoo_shopping_tw`, `gmarket` |
| `dept-store` | First-party, broad, non-grocery-led | `mustafa_online` |
| `pharmacy` | Dispensing / medicines-led | `watsons`, `boots` |
| `cosmetics` | Cosmetics / personal-care-led, non-dispensing | `cosmed` |
| `electronics` | Consumer electronics / appliances | `fptshop_vn`, `singer_lk` |
| `home-improvement` | Hardware, DIY, building materials | *(none yet)* |
| `fashion` | Apparel and footwear | *(none yet)* |
| `pet` | Pet food and supplies | *(none yet)* |
| `wholesale` | Wholesale market / trade feed, not consumer retail | `moa_wholesale`, `talaadthai` |
| `fuel-station` | Forecourt retail (the `fuel` pipeline is separate) | *(none in prices)* |
| `real-estate` | Property listing portal — a genuine division-04 rent source | `propertyguru_my`, `lamudi_ph` |
| `other` | Legal and tracked. Accumulation is the signal to add a value. | `hotpepper_jp` (dining) |
| `aggregator` | **RETIRING (Task 7).** Do not use for new sources. | *(126 manifests being retagged)* |

<!-- channel-values:end -->

  `null` remains correct for non-product sources (CPI publications, NSO
  averages, tariffs, cost-of-living surveys); `analytical_role` carries the
  meaning there.
- **`data/prices/enrich/`** — the single enrich home (no underscore): curated
  `gold/`/veto/denylist alongside working artifacts (`products_input.parquet`,
  `cache/`, `_models/`, embed caches).

### Live CLI verbs
`collect`, `backfill`, `common-crawl`, `process`, `eval`, `match-record`,
`census`, `train-classifier`, `label`, `build`, `publish`.
(There is **no** `prices classify` verb — see Retired.)

---

## Retired — do NOT use

The KNN/HNSW tier-b/tier-c cascade and its improvement loop were **removed
2026-07-24**. No live code path reads these artifacts or symbols; the residue is
in docs, comments, prompts, and orphan files. If you find one of these presented
as current, it is stale.

| Retired term / artifact | Current replacement |
|---|---|
| tier-b, tier_b, KNN, HNSW, cluster_key, cluster_agreement | (embedding → head) classifier; no clustering |
| tier-c, tier_c, "KNN-aware LLM reranker", tier-c escape rate | veto pass + global `tau` gate (no LLM on the classify hot path) |
| canonical_strict (as cluster key) | `input_hash` structural key |
| enrichments.parquet | classified.parquet (keyed by `input_hash`) |
| sub_label_id, sub-vocabulary, `_sub_labels_store.json`, `_sub_labels.parquet`, `_class_tree.json`, `_retrieval_legacy.parquet` | `coicop_code` at the deepest leaf (no sub-grain) |
| oracle, blind set, gold v3, `_gold_v3_misses.csv`, iteration gate, cascade-iter branch, disagreement set, headline scalar | gold v5 (`_load_gold()`); `prices eval` / `head_eval.py` OOF coverage |
| base_items, base_items.parquet, gazetteer.parquet, validation_runs/, CANDIDATE / GREEN, `prices classify` | none — no such subsystem in live code; use `prices process` + `train-classifier` + `eval` |
| consensus / witness (cascade multi-model sense) | veto + audit layers (keep "consensus" only for gold two-labeler agreement) |
| `_enrich/` scratch dir | `enrich/` (the single live home) |
| boilerplate strip in `prepare` | removed (−4.5pp regression); the RAW name is fed to the embedder |

### Known stale references (recorded, not yet fixed)
These live files still carry retired vocabulary (backlog, see the session note):
`enrich/boilerplate.py` (dead, cites tier-b), `enrich/prompts/enrich_system.md`
(emits `sub_label_id`, byte-hashed by `versioning.py`), `enrich/normalize.py:286`
("tier-b passage augmentation" comment), `configs/_examples/template.yaml` +
`momo_tw.yaml` + `laostatefuel.yaml` (tier-b/c rationale), `enrich/rate_limit.py`
("tier-c" wording), the three cascade-era skills. Phantom doc anchors (`§9`,
"Recorder data path") in `match_record.py`, `census.py`, `audit_monitor.py`,
`compare_extractors.py` point to specs not present under `src/prices/`.
