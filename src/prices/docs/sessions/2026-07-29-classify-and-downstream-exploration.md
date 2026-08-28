# 2026-07-29 — First full classify + downstream feedback exploration

## Goal

With the full 7,680-d ensemble banked ([[2026-07-29-full-ensemble-embed]]),
produce the first full **`classified.parquet`** over the F&B survivors, inspect
the quality of the post-embedding classification (using confidence, gold, vetoes,
and the basis audit), and explore how the results feed back into the system —
labeling, vetoes, regex, and downstream consumable data. EAP + COICOP division 01.

## Part 1 — Writing `classified.parquet`

**The blessed head is now the ensemble.** `v11` loads with `feat_dim=7680`,
194 leaves, `tau=0.7885`, division 01 — i.e. it was trained on the full
0.6B+4B+8B concat, resolving the earlier "ensemble UNBLESSED / 4B-only head"
gotcha (`prices_blessed_head_4b_only_ensemble_unblessed_20260727`). Store and head
are dimensionally aligned.

Ran `python run.py prices process --stage classify` (uncapped). Because all three
tags are banked, `batch_embed._build_store` finds `missing == {}` and skips
straight to predict: score 256 buckets from stored fp16 vectors
(`_classify_pred/v11/pred_<b>.parquet`), then expand back over all 2,007,881
`products_input` rows with regex `extract()` + the basis audit per row.

**Output: 224,650 division-01 rows** at `data/prices/enrich/cache/classified.parquet`
(keyed by `input_hash`). States: **224,046 `classified` / 604 `flagged_basis`**,
0 audit-rejects, 0 `narrow_source`. Head-rejected survivors (null code) are dropped
by the `startswith("01")` filter — `classified.parquet` is the accepted,
downstream-consumable view; the richer per-survivor substrate (rejects included)
lives in the pred shards.

## Part 2 — Quality report (three lenses)

A reusable report (`quality_report.py`, job-tmp) over the gold OOF machinery + the
banked vectors + the write.

**Lens A — gold OOF (the honest number).** 8,182 gold rows / 194 leaves,
`tau@98%=0.7885` → **precision 98.1% / coverage 61.1%**. The reliability curve is
well-calibrated (conf 0.65→82%, 0.82→95%, 0.93→98%, 0.98→99.5% accuracy), which is
what justifies a single global gate. Coverage@precision sweep:

| target precision | tau | coverage |
|---|---|---|
| 96.7% | 0.70 | 69.1% |
| **97.1% (measured)** | **0.7241** | **67.2%** |
| **98.1% (blessed)** | **0.7885** | **61.1%** |
| 98.5% | 0.85 | 53.0% |

So the τ lever is a **measured +6.1pp coverage for −1.0pp precision** at 0.7241.
Veto lift on gold is tiny (98.0→98.1%) — gold is clean; vetoes earn their keep on
wild data.

**Lens B — wild.** 118,218 / 381,228 survivors accepted (**31%**) = 7.5% of the
1.585M-name corpus. The accept cliff sits exactly at τ. Existing vetoes fired
**440 rejects on wild** (vs 28 on gold), concentrated in nuts `01.1.6.9.4` (148)
and soft drinks `01.2.6.0.0` (99) — processed/adjacent forms.

**Overlay — gold ∩ wild.** Realized precision **99.9% (6515/6523)** on the gold
names present in wild. ⚠️ In-sample (v11 trained on all gold), so this **confirms
the embed→head→veto wiring is bug-free end-to-end**, but is NOT a generalization
estimate — the honest number stays the OOF 98.1%. Only **8 disagreements**, all
near-miss siblings.

**Basis audit.** 604 `flagged_basis` (extracted basis contradicts the leaf
denylist → quarantined, not dropped), 0 hard rejects.

Detail: `prices_classified_written_quality_report_20260729`.

## Part 3 — Downstream feedback exploration (5 Sonnet agents)

Dispatched five read-only/propose-only agents, one per feedback lens: **labeling
rounds, veto/trap mining, regex/flagged_basis, downstream consumable data, and a
meta feedback-flywheel**. (A mid-run Anthropic API capacity event — 500s / 529
Overloaded — killed the first batch; all five were relaunched and completed.)

**Three biggest levers (deduplicated across agents):**

1. **`SOLD_BY_ITEM_LEAVES` (`build/sold_by_item.py`) is empty** → 43.8% of rows
   (96,306) quarantine as `review_missing_qty`. Authoring it (human-gated pilot on
   soft drinks / water / bread) moves downstream **trusted yield 45.9% → ~85%**.
   Honest ceiling: 99.4% of those rows genuinely lack a pack-size in the scraped
   name — a data-completeness limit, not a bug.
2. **Re-run `prices build`** — on-disk outputs are stale (Jun 8) while the Layer-2
   unit-value audit + QA rollup shipped 2026-07-24 and `classified.parquet`
   regenerated today. **Zero-cost**, unblocks all downstream + the monitor scripts.
3. **Alcohol RTDs mis-filed as soft drinks `01.2.6.0.0`** — a veto set
   (gin/vodka/rum/whisky/`\balc\.?\s*\d`/guarded `\bbeer\b`) catches **+104 wild
   rows**, all proven 0 gold-collision (div-01 excludes alcohol).

**Measured downstream funnel** (224,650 → trusted): trusted **103,150 (45.9%)** /
`review_missing_qty` 96,306 / `review_uv_outlier` 20,252 / `review_fx` 208.
Coverage matrix: 1,140 usable (leaf, country) cells @ n≥5 — strong for
Cambodia/PH/Thailand/MY/SG/JP/HK/AU; 8 small-Pacific nations have data but 0
usable (thin-cell); American Samoa zero.

**Other workstream headlines:**

- **Regex:** the largest flagged_basis cluster (293/604) is the **liquid-by-weight
  EAP convention** (juice/soda/water labeled in grams) — regex is *correct*, the
  denylist is too strict → relax it / add density≈1 mass→volume at the audit layer
  (clears half the backlog, zero regex risk). Clean bugs: JP produce size-grade
  `2L/3L`→liters (n=59, also lifts weakest script kana), `mg/L` mineral clause
  (n=7), water-bottle capacity (n=3). **Thai fires 0/30 because no Thai unit
  lexicon exists** → add `_VALUE_UNIT_TH` mirroring the working `_VALUE_UNIT_ZH`
  (tops_th is live in EAP).
- **Labeling:** the below-τ convertible mass splits 45% catch-all/n.e.c. (won't
  help) + 23% saturated-real (won't help; verdict predates v11) + **10% GROW
  (actionable)** → Round-13 = top 25 thin *specific* leaves, ~550 net-new rows,
  script-stratified, est. +1.5–2.5pp coverage.
- **Flywheel:** keep the single global τ and the 98% bless floor; run the 0.7241
  point as a logged, human-reviewed experiment (Layer-2 does **not** backstop
  leaf-precision errors). The `--bless` gate is too thin today (only overall
  precision −2pp) — add coverage-regression, per-leaf floor, veto-collision
  recheck, and a stale-pin grep.

**Cross-cutting insights the agents converged on:**

- **The basis audit doubles as a classifier-error detector.** RTD coffee →
  ground-coffee leaf (n=94) and mouthwash → confectionery (n=35) are *classifier/
  gold* errors surfacing through `flagged_basis` — so the 604 rows are a free,
  high-precision **mining pool** for the veto + labeling loops, not just regex QA.
- **Confidence is a dead lever downstream** — median ≈0.94 across trusted /
  review / outlier alike; do not add a confidence threshold in `build`.

**Two verified code bugs** (confirmed by direct grep):
`enrich/scripts/audit_monitor.py:49` hardcodes `load_predictor("v6")` (latest is
v11; the only hardcoded pin in `enrich/`), and `classifier/evaluate.py` is dead
(imports `EVAL_REPORT_FILE`/`EXCLUDE_CLASS`/`REJECT_CLASSES` no longer in
`__init__.py`; reads single-round `gold_v5_final.parquet`).

Full synthesis: `prices_feedback_roadmap_5agent_20260729`.

## Artifacts

- `data/prices/enrich/cache/classified.parquet` — 224,650 div-01 rows (the write).
- `data/prices/enrich/_classify_pred/v11/pred_*.parquet` — 256 per-bucket pred shards.
- Job-tmp: `quality_report.py`; `wild_predictions.parquet` (381,228-row substrate:
  name/raw_leaf/conf/action/leaf/accepted); `wild_gold_disagreements.parquet`.

## Next session

Execute the roadmap, lowest-risk first: **Phase 0** (re-run `prices build`; fix the
two bugs), then **Phase 1** precision feedback (append the 10 vetoes + regex fixes
+ denylist relax, re-eval), then **Phase 2** author `SOLD_BY_ITEM_LEAVES`, then
**Phase 3** Round-13 labeling → retrain → bless through a hardened gate.

## Notes / gotchas

- All Part 3 work was **read-only/propose-only** — nothing implemented or committed.
- Work done **in place**; commits require explicit user go.
- Reconciliation backlog: `ENRICH.md`'s migration-status note should record that
  v11 (the 7,680-d ensemble) is now the blessed head and that `classified.parquet`
  is written at full scope — not done this session (docs-only session).
