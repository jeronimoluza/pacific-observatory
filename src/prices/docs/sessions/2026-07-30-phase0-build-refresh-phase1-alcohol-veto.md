# 2026-07-30 — Phase 0 build refresh + Phase 1 precision (alcohol veto shipped)

## Goal

Execute the downstream roadmap from the 5-agent synthesis
([[2026-07-29-classify-and-downstream-exploration]]). User picked **Phase 1
(precision)** after Phase 0. Work done **in place** (worktrees off; `data/`+`.venv`
live only in the main checkout, so a worktree would break the data-dependent
build/eval). Nothing committed.

## Phase 0 — build refresh (zero code change)

`data/prices/build/` outputs were stale (Jun 8) while `classified.parquet`
regenerated Jul 29. Ran `.venv/bin/python run.py prices build` (system python3.14
lacks `click` — must use `.venv`). Fresh outputs (dir is `build/`, **not** `_build/`
— CLAUDE.md doc drift): snapshot 219,916 / observations 1,077,090 / trusted
760,940 / unit-value summary 20,066 cells. Funnel: **trusted 46.9% /
review_missing_qty 43.8% / review_uv_outlier 9.2% / review_fx 0.1%**, 1,140 usable
(leaf,country) cells @ n≥5.

## Phase 2 ceiling — REFINED (synthesis's 45.9%→85% is over-optimistic)

Read-only diagnostic on the 96,306 `review_missing_qty` rows (all `item`-basis;
names in `product_name_original`, retained in snapshot + products_input):

- **~41.5%** are packaged-by-weight/volume (dairy/juice/coffee/water/soft
  drinks/formula/cereal/confection) — item-basis unit values are meaningless there;
  **correctly quarantined**, a data-completeness floor, NOT recoverable by
  `SOLD_BY_ITEM_LEAVES`.
- Only **~14%** is fresh produce, and even those divisions' biggest leaves are
  packaged snacks (nuts `01.1.6.9.4`, chips/relish `01.1.7.9.9`, fries `01.1.7.9.4`)
  that must be excluded.
- Only **1.7%** (1,634) carry a missed `pc/pcs` token (deterministic count-regex
  fix, mostly "1 pc" singles).

**Realistic precision-safe ceiling: ~+10–15pp (→ ~57–62% trusted), not +40pp.**
The rest is a scrape-completeness limit (names lack pack size) — a collect-side fix.

## Phase 1 — precision (alcohol veto SHIPPED + materialized)

**Alcohol RTDs mis-filed as soft drinks `01.2.6.0.0`.** Appended 3 regex vetoes to
`data/prices/enrich/gold/veto_lexicon.parquet` (168→171; backup
`veto_lexicon.parquet.bak-20260730T142217Z`), `source=phase1_alcohol_20260730`:

1. `\b(gin|vodka|rum|whisk(?:e)?y|brandy|tequila)\b`
2. `\balc\.?\s*\d`  (ABV, e.g. "Alc. 5%")
3. `(?<!root )(?<!ginger )(?<!birch )\bbeer\b`  — **guard mandatory**: naive
   `\bbeer\b` wrongly rejects 5 real gold soft drinks (Root Beer ×4, Ginger Beer
   ×1, all true `code=01.2.6.0.0`); the guard drops exactly those → 0 collision.

**Verified before shipping:** (a) 0 gold-collision on `code` for every pattern;
(b) gin FP-audit clean (word boundary excludes virgin/ginger/ginseng, 0 FP/115);
(c) single-embed gold OOF eval (embed gold once, overlay veto) — baseline
prec 0.9806/cov 0.6107 → +alcohol **0.9808**/0.6107, tp 4997 unchanged (removes
1 gold false-accept, 0 TP lost).

**Materialized end-to-end** (no re-embed — all 3 tags banked):
- classified.parquet 224,650 → **224,320** (330 alcohol rejected); soft drinks
  11,992 → **11,662**, 0 alcohol remaining.
- Rebuilt downstream: trusted ship set 760,940 → **759,901** (−1,039 alcohol obs);
  **0 alcohol in the 46,528 trusted soft-drink observations**.

### Gotcha — pred-shard cache blocks veto/regex changes

`prices process --stage classify` **reuses cached** `_classify_pred/<ver>/pred_*.parquet`
(`batch_embed._predict_bucket:60`); the veto runs inside `predict.score_matrix`,
which only executes when a shard is (re)built. So editing `veto_lexicon.parquet` +
re-running classify had **no effect** (first attempt: 3.5 min, count unchanged).
Fix: point `pred_root` at a fresh empty dir to force re-score (no embed —
`_build_store` no-op since `embed_store.missing=={}`). **Monkeypatching
`batch_embed.PRED_DIR` fails** (default arg `pred_root=PRED_DIR` binds at def-time);
patch the function: `batch_embed.embed_and_predict = functools.partial(orig,
pred_root=fresh)`. Always regen shards after any veto/extract-regex edit.

## The other Phase 1 items are NOT clean precision wins (investigated, deferred)

- **Denylist relax (293 "liquid-by-weight")** — NOT a safe blanket op. The 296
  mass-flagged rows on juice/water/soft-drinks are a mix: genuine juice-by-weight
  (~half of juice) + **powders** (Powerade PWD 500g — different product form) +
  **misclassifications the audit correctly catches** (water bottles=hardware,
  purification tablets, cola candy, a cosmetic "Soda" lip tint) + mg/L
  mineral-spec misreads. Blanket relax would ship those as trusted → hurts
  precision. Safe path = density≈1 conversion targeted at confirmed juice only.
- **Coffee/confectionery/citrus `volume` flags** are correctly-flagged classifier
  errors (RTD coffee→ground coffee n=95, mouthwash→confectionery n=64, JP produce
  grade n=50) — feed the veto+labeling loop, not a relax. (Confirms the "basis
  audit = classifier-error detector" cross-cutting insight, strongly.)
- **JP `2L`/`3L`** — same token = liters for beverages (correct) vs size-grade for
  produce; disambiguation is COICOP-context multi-token, regression-risky, and the
  audit already quarantines the wrong ones → coverage-recovery, not precision.
- **Thai lexicon** — coverage (Thai currently 0/30), not precision.

## Two verified bugs (still open — Phase 0 step 2, not done)

`enrich/scripts/audit_monitor.py:49` hardcodes `load_predictor("v6")` (latest v11);
`classifier/evaluate.py` is dead (ImportError on removed symbols).

## Next session

Materialize the veto is DONE. Remaining, by value: (1) the two bug fixes (trivial);
(2) targeted density-conversion for juice-by-weight + route RTD-coffee/mouthwash
flags to veto/labeling; (3) conservative `SOLD_BY_ITEM_LEAVES` (whole-produce only)
for the realistic ~+10-15pp; (4) Phase 3 Round-13 labeling. Commit this session's
veto + docs on user go.

## Artifacts

- `data/prices/enrich/gold/veto_lexicon.parquet` (+3 rows; backup alongside).
- `data/prices/enrich/cache/classified.parquet` (224,320 rows, veto applied).
- `data/prices/build/eap_fnb_*.parquet` (rebuilt, alcohol-free trusted series).
