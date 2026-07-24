# Prices Enrich — architecture & design rationale

Turns raw scraped product rows into structured, COICOP-classified, trust-graded
price observations. Lives under `src/prices/enrich/` (+ `src/prices/build/` for
aggregation). This file documents the **live** design and *why* it is shaped
this way. The retired KNN/HNSW + LLM-reranker cascade (tier-b/tier-c) was removed
2026-07-24; any tier-b/tier-c/KNN/consensus/witness term is dead history.

## Pipeline

```
collect → outputs/prices/raw/raw_prices.csv        (per-source spiders/fetchers)
    │
    ▼  prices process   (STAGE_ORDER in enrich/cli.py)
  concatenate → outputs/prices/raw/raw_prices.csv   (unify raw_items/wayback/CC → one CSV)
  prepare     → data/prices/_enrich/products_input.parquet   (dedup to one row / input_hash)
  taxonomy    → static/coicop_subcategories.json    (Gemini-derived leaf sub-vocab)
  classify    → data/prices/_enrich/cache/classified.parquet
  merge       → outputs/prices/enriched/enriched_prices.csv   (raw × enrichment, per obs)
    │
    ▼  prices build   (build/aggregate.py)
  eap_fnb_snapshot.parquet   (from products_input, dated today)
  eap_fnb_observations.parquet (from raw CSV, monthly history)
    │
    ▼  prices publish → outputs/prices/eap_fnb_dashboard.html
```

## Two independent jobs on each product name

The `classify` stage runs two *independent* enrichers per unique name and
overlays both onto the row:

1. **Structural extraction** (`extract.py` + `regex_patterns/`) — deterministic
   regex that resolves `pricing_basis`, `amount_value`, `standard_unit`,
   `count`, `multiplier`, and promo flags. Never decides COICOP. This is the
   stable, high-value core.
2. **COICOP classification** — an embedding of the **raw** product name
   (Qwen3-Embedding-4B) → a logistic-regression head predicting the COICOP leaf,
   then a veto pass. Feeds only `coicop_code` + `confidence`.

They are independent by design: the structural fields are a physical fact about
the name (how it's priced), the leaf is a semantic judgment. Keeping them
separate means a bad parse can't corrupt the label and vice-versa, and each is
audited on its own terms downstream (Layer-1 uses both; Layer-2 uses the leaf).

## Design decisions & why

**Identity / hashing (`prepare._row_input_dict` + `versioning.input_hash`).**
The dedup key is `(product_name, product_url)` when a URL exists, falling back to
`(product_name, country, currency)` when it doesn't. *Why:* live Scrapy rows
always carry a URL, but wayback/common-crawl rows often don't; if URL were
mandatory every URL-less row would collide into one empty-URL bucket and distinct
products would merge. The `(country, currency)` fallback is the conservative
partition that avoids that. The fallback intentionally has no `date`, so repeat
captures of the same name/market collapse and are median-priced — `products_input`
is a dedup *identity* table, not an observation log (per-observation history is
kept in `raw_prices.csv`). `input_hash` is a pure structural hash, decoupled from
prompt/taxonomy version.

**Feed the RAW name to the embedder.** No boilerplate strip, no
normalization/canonicalization before embedding — it is a measured ~-4.5pp
regression. The `prepare` boilerplate strip was removed for this reason.

**Single global tau, derived out-of-fold.** `train.py` fits the LR head on 100%
of gold, but derives the accept threshold `tau` from 5-fold out-of-fold
predictions at the target precision (cov@98). *Why global, not per-leaf:*
per-leaf taus miscalibrate on out-of-distribution names. `eval/head_eval.py`
reports the honest OOF coverage; there is no separate held-out test set.

**Count vs multiplier (`merge.compute_unit_value`, "Convention A").** For
mass/volume/length the `amount_value` is the pack TOTAL, so only `multiplier`
(identically-priced sub-packs) divides the unit-value denominator; the piece
`count` is captured but never multiplies a total weight. This removes the
count×amount double-count (e.g. "Laughing Cow 10s 200g" → $/kg on 200g, not 20g).

**Vetoes — REJECT vs REROUTE (`vetoes.py`, `veto_lexicon.parquet`).** A per-leaf
lexicon of regex/phrase traps applied to accepted predictions. REJECT withholds
the prediction (needs `gold_positive_collisions=0`). REROUTE rewrites the leaf
(e.g. cola+sour+no-volume → confectionery) and is held to a *higher* bar
(zero gold collisions on the source AND corpus-verified target precision) because
it injects a positive value rather than merely withholding one.

## Trust model — two audit layers, precision-first

The consumable deliverable is rows where **`trust_level=="high"` (Layer-1) AND
`trust_uv=="high"` (Layer-2)**. Both quarantine rather than fabricate; neither
mis-rejects.

- **Layer-1 basis audit** (`audit.py` + `basis_denylist.parquet`). Rejects/flags
  physically-impossible `(coicop_leaf, pricing_basis)` pairs. `action="reject"`
  only when `semantic=="HIGH" AND evidence_state=="CONFIRMED"`, else `"flag"`.
  Denylist rows currently cold-start `UNOBSERVED`, so today every hit is a FLAG
  (REJECT is reachable only after a human promotes a leaf via `audit_monitor.py`).
- **Layer-2 unit-value audit** (`build/unit_value_audit.py`). Statistical outlier
  detection per **`(coicop_code, country)`** cell: log-space, per-month median
  detrend, robust `median ± 3·MAD` on pooled residuals. Abstains (`trust_uv="flag"`,
  never rejects) on thin cells (n<5) or zero-spread. Snapshot (all rows dated
  today) degenerates to plain cross-sectional MAD. The cell is `coicop_code` at
  the deepest leaf the classifier assigns — the retired cascade's finer
  `sub_label_id` is no longer produced; the leaf is never rolled up so distinct
  products stay separate wherever the taxonomy separates them. Coarser than
  sub_label_id ⇒ under-covers (withholds more) but never mis-rejects.

Two read-only monitors surface candidates for human triage without mutating
build output: `scripts/audit_monitor.py` (Layer-1 `(leaf, basis)` contradictions)
and `scripts/uv_audit_monitor.py` (Layer-2 unit-value outliers).

## build/aggregate wiring

`prices build` joins `classified.parquet` to the price side on **`input_hash`**
(exact — classify inherits `products_input`'s hash unchanged, so the old
name/country/currency triple workaround is gone). Snapshot joins
`products_input`; observations recompute `input_hash` per raw-CSV chunk via the
same `_row_input_dict` basis. `load_filtered_cache` keeps F&B-prefix ×
`state∈{narrow_source,classified}` × `trust_level=="high"`. `_finalize` then:
canonicalize unit per leaf → compute unit_value → Layer-2 flag → attach FX/USD.

## Live glossary

- **Structural extraction / "tier-a"** — the regex enricher (`extract.py`); the
  only surviving "tier" term. Overlays quantity fields, never COICOP.
- **(embedding → head) classifier** — the live COICOP classifier. Canonical name.
- **Narrow source** — a source whose declared `coicop_codes` share one 3-digit
  prefix; its rows short-circuit to the declared code (`state="narrow_source"`).
- **Declared `coicop_codes`** — per-source YAML COICOP commitment, written at
  onboarding.
- **`products_input.parquet`** — dedup identity table (one row / input_hash),
  the classify input. Distinct from `products.parquet` (the `prices census`
  coverage grain) and the dead `enrichments.parquet`.
- **`data/prices/enrich/`** (no underscore) — curated gold/veto/denylist home.
  **`data/prices/_enrich/`** (underscore) — working/scratch dir. Do not confuse.
- **`prices classify <base_item>`** — the `base_items/` GREEN-promotion tool, a
  *separate* CLI verb from the `classify` stage inside `prices process`.

## Regex patterns tree

`regex_patterns/` houses tier-a patterns as typed modules composed by a grammar
of M (measure) / C (count-noun) / P (pack) / B (per-unit basis) productions over
vocab YAMLs (`vocab/{units,count_nouns,pack_basis}.yaml`). CJK records stay
hand-written in `buckets/`. `_registry.py` pins the pattern order; `dict_view.py`
adapts the tree to the dict shapes `extract.py` consumes. Byte-identity between
the composed tree and the pre-refactor modules is guarded by
`tools/compare_extractors.py` + the layout/equivalence tests. See
`REGEX_PATTERNS.md` for the plain-English extraction contract.
