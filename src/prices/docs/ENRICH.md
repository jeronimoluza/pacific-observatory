# Prices — Enrich (design & rationale)

The deep-dive on the `process`/`classify` stage: how raw scraped product rows
become structured, COICOP-classified, trust-graded observations, and **why** it is
shaped this way. Folds the former `src/prices/enrich/CONTEXT.md`. For the whole
pipeline map see `ARCHITECTURE.md`; for terms see `GLOSSARY.md`.

The retired KNN/HNSW tier-b/tier-c cascade (removed 2026-07-24) is **not** part of
this design. Any tier-b/tier-c/KNN/oracle/gold-v3 term is dead history.

## Two independent jobs on each product name

The `classify` stage runs two *independent* enrichers per unique name and overlays
both onto the row:

1. **Structural extraction** (`extract.py` + `regex_patterns/`) — deterministic
   regex that resolves `pricing_basis`, `amount_value`, `standard_unit`, `count`,
   `multiplier`, and promo flags. Never decides COICOP. The stable, high-value core.
2. **COICOP classification** — an **ensemble embedding** of the **RAW** product
   name (`embedding.py`) → a logistic-regression head predicting the COICOP leaf,
   then a veto pass. Feeds only `coicop_code` + `confidence`.

They are independent by design: the structural fields are a physical fact about the
name (how it is priced); the leaf is a semantic judgment. Keeping them separate
means a bad parse can't corrupt the label and vice-versa, and each is audited on
its own terms downstream (Layer-1 uses both; Layer-2 uses the leaf).

## Design decisions & why

**Identity / hashing** (`prepare._row_input_dict` + `versioning.input_hash`).
The dedup key is `(product_name, product_url)` when a URL exists, falling back to
`(product_name, country, currency)` when it doesn't. *Why:* live Scrapy rows always
carry a URL, but wayback/common-crawl rows often don't; if URL were mandatory,
every URL-less row would collide into one empty-URL bucket and distinct products
would merge. The `(country, currency)` fallback is the conservative partition that
avoids that. The fallback intentionally has no `date`, so repeat captures of the
same name/market collapse and are median-priced — `products_input` is a dedup
*identity* table, not an observation log (per-observation history lives in
`raw_prices.csv`). `input_hash` is a pure structural hash, decoupled from
prompt/taxonomy version.

**Feed the RAW name to the embedder.** No boilerplate strip, no normalization or
canonicalization before embedding — it is a measured ~−4.5pp regression. The
`prepare` boilerplate strip was removed for this reason. (`boilerplate.py` still
exists on disk but is dead code — see the backlog in the session note.)

**Ensemble embedder — concat of 0.6B + 4B + 8B** (`embedding.py`). The head is fit
over the CONCATENATION of three frozen Qwen3-Embedding encoders — 0.6B (1024-d) +
4B (2560-d) + 8B-q8 (4096-d) → 7680-d. Each block is L2-normalized *independently*,
then concatenated with **no global renorm** (each block stays unit-norm; the full
vector has norm √3). *Why:* per-block L2 is the whole trick — it stops any one
encoder dominating by raw magnitude — and the concat is the single biggest cov@98
lever, lifting div-01 gold from ~47% (single-4B) to ~63%. The block **order is
load-bearing**: it fixes the column layout the head learned, so predict must
reproduce it exactly (guarded by config order + provenance `embed_models` in the
bundle).

*Backend is mixed by block*, matching the recipe that produced ~63%: the 0.6B is
encoded in-process by sentence-transformers at seq-len 48; the 4B and 8B go through
`mlx_embeddings` in the sibling `.venv_mlx` (seq-len 512) via a subprocess to
`embedding_mlx.py`. *Why mixed:* the 8B only fits 16 GB as an 8-bit mlx build, and
only the locally-converted q8 dir (`config.MLX_8B_MODEL_DIR`, model_type=`qwen3`)
loads — the HF `tierralibre/…-q8` id does not; the 0.6B is the block the recipe
encoded with ST. Per-block vectors are cached on disk keyed by raw name
(`block_{tag}.npz`), so the gold/corpus overlap and repeat runs never re-embed — a
fully-cached call touches neither the ST model nor the mlx subprocess.
Knobs: `MLX_8B_MODEL_DIR`, `MLX_VENV_PYTHON`.

**Prediction-shard cache + the veto-staleness gotcha** (`classifier/batch_embed.py`).
Separate from the per-block embedding cache, head scores are cached per name-bucket
under `_classify_pred/<head_version>/pred_NNN.parquet`. `_predict_bucket` reuses a
shard whenever its cached names cover the requested names, so a bucket the incoming
batch does not grow keeps scores computed *before* any later veto-lexicon change —
silently reverting that veto. `prices process --stage classify --rebuild` now
`rmtree`s `_classify_pred` (`cli._invalidate_for`) to force a fresh score from the
banked embeddings; this re-scores, it does **not** re-embed (the block cache is
untouched). Always pass `--rebuild` to classify after editing `veto_lexicon.parquet`
or folding in a new source batch.

**Single global tau, derived out-of-fold** (`classifier/train.py`). Fits the LR
head on 100% of gold, but derives the accept threshold `tau` from 5-fold
out-of-fold predictions at the target precision (cov@98). *Why global, not
per-leaf:* per-leaf taus miscalibrate on out-of-distribution names.
`eval/head_eval.py` reports the honest OOF coverage; there is no separate held-out
test set.

**Gold** (`classifier/dataset._load_gold()`). Trains **and** evaluates the head.
Canonical gold is the `_load_gold()` union of `gold_v5_*` parquets under
`data/prices/enrich/gold/` (~14.4k rows). `gold_v5_8k_final.parquet` is only the
anchor, not the whole set. `gold_labels.parquet` is an older, separately-schema'd
consolidation **not** read by the classifier. The gold-growth loop (`prices label`)
dispatches batches to codex + gemini, keeps only rows where the two labelers agree
(the live "consensus"), and fires opus to adjudicate hard cases.

**Count vs multiplier** (`merge.compute_unit_value`, "Convention A"). For
mass/volume/length the `amount_value` is the pack TOTAL, so only `multiplier`
(identically-priced sub-packs) divides the unit-value denominator; the piece
`count` is captured but never multiplies a total weight. This removes the
count×amount double-count (e.g. "Laughing Cow 10s 200g" → $/kg on 200g, not 20g).

**Vetoes — REJECT vs REROUTE** (`vetoes.py`, `veto_lexicon.parquet`). A per-leaf
lexicon of regex/phrase traps applied to accepted predictions. REJECT withholds
the prediction (needs `gold_positive_collisions=0`). REROUTE rewrites the leaf
(e.g. cola+sour+no-volume → confectionery) and is held to a *higher* bar (zero gold
collisions on the source AND corpus-verified target precision) because it injects a
positive value rather than merely withholding one.

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
  detrend, robust `median ± 3·MAD` on pooled residuals. Abstains
  (`trust_uv="flag"`, never rejects) on thin cells (n<5) or zero-spread. Snapshot
  (all rows dated today) degenerates to plain cross-sectional MAD. The cell is
  `coicop_code` at the deepest leaf the classifier assigns — the retired cascade's
  finer `sub_label_id` is no longer produced; the leaf is never rolled up so
  distinct products stay separate wherever the taxonomy separates them. Coarser
  than sub_label_id ⇒ under-covers (withholds more) but never mis-rejects.

Two read-only monitors surface candidates for human triage without mutating build
output: `scripts/audit_monitor.py` (Layer-1 `(leaf, basis)` contradictions) and
`scripts/uv_audit_monitor.py` (Layer-2 unit-value outliers).

## build/aggregate wiring

`prices build` joins `classified.parquet` to the price side on **`input_hash`**
(exact — classify inherits `products_input`'s hash unchanged). Snapshot joins
`products_input`; observations recompute `input_hash` per raw-CSV chunk via the
same `_row_input_dict` basis. `load_filtered_cache` keeps F&B-prefix ×
`state∈{narrow_source,classified}` × `trust_level=="high"`. `_finalize` then:
canonicalize unit per leaf → compute unit_value → Layer-2 flag → attach FX/USD.

## Regex patterns tree

`regex_patterns/` houses tier-a patterns as typed modules composed by a grammar of
M (measure) / C (count-noun) / P (pack) / B (per-unit basis) productions over vocab
YAMLs (`vocab/{units,count_nouns,pack_basis}.yaml`). CJK records stay hand-written
in `buckets/`. `_registry.py` pins the pattern order; `dict_view.py` adapts the
tree to the dict shapes `extract.py` consumes. Byte-identity between the composed
tree and the pre-refactor modules is guarded by `tools/compare_extractors.py` + the
layout/equivalence tests. See `../enrich/REGEX_PATTERNS.md` for the
plain-English extraction contract.

## Live glossary pointer

Term definitions (tier-a, ensemble embedder, tau, veto, trust levels, narrow
source, input_hash, gold v5) live in `GLOSSARY.md`, which also carries the
authoritative **Retired — do not use** table.
