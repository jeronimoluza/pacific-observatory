# 2026-08-04 — Gold quality audit + labeling-architecture strategy (+ wholesale channel)

## Goal

Two threads. (1) The sourcing sweep for the 57 under-covered div-01 leaves kept
concluding "the product is already in the corpus" — so the real question became
**why the classifier can't reach those leaves**, which is a *gold* problem, not a
sourcing one. (2) With that established, decide the **accurate + token-efficient**
architecture for labeling gold and classifying observations — is the cheap
`codex + gemini → opus-on-disagreement` ensemble good enough, or do we need a
bigger model / better prompt?

Bookended by a wholesale-sourcing deliverable (the one genuine *sourcing* gap).

## Why we keep landing on gold labeling

The head is a **closed-set** logistic regression: its output classes are exactly
the COICOP leaves with **≥ MIN_SUPPORT (5)** gold rows. A leaf with 0–4 gold rows
*does not exist as an output* — matching products get force-routed to the nearest
in-head sibling, or dropped below tau. So every leaf has **two independent gates**:

- **Corpus gate** (sourcing): are the raw products collected at all?
- **Label gate** (gold): does the leaf have ≥5 gold rows so the head can emit it?

Most div-01 gaps are **label-gated, not source-gated** — the products are already
collected, they just pile up on the wrong sibling. That is why sourcing sweeps
keep bottoming out at "grow/clean gold."

The gold target set is *not* "every leaf" — it is every **reachable** leaf: has
EAP corpus, is not a `.9` catch-all, is not a service. True-zeros (fresh
cranberries, yautia, live rabbits) must **not** be seeded — a class the head can
predict but nothing legit matches only manufactures false positives.

## Structural audit — gold is structurally clean

Validated the classifier's actual training table (`_load_gold()`, **14,911 rows**)
against the repo leaf set `data/prices/enrich/gold/coicop_leaves.txt` (538 valid
leaves; tab-separated `code\ttitle` — split on tab before comparing).

| Check | Result |
|---|---|
| distinct off-taxonomy codes | 23 |
| off-taxonomy rows | 192 — of which **129 empty `exclude`** + 63 shallow/malformed |
| off-taxonomy codes reaching the trained head | **~1** (`01.1.6`, group-level fruit) |

**Malformed/invalid codes are not the lever.** The real exposure is **convention
errors**: a row with a *valid* leaf that is the *wrong valid leaf* — invisible to
structural validation, and the systematic blind spot of agree-filtering (agreement
cancels variance, not shared bias).

## Convention audit — note-grounded fleet

Workflow `coicop-convention-audit`: 14 Sonnet shards over all **231 div-01 gold
leaves / 8,665 valid-leaf rows**, each fed the leaf's **official COICOP inclusion
note** (from `coicop_categories.csv` `keywords`); Opus adjudicated **only the
flags** (token-efficient — the clean rows never reach Opus).

**38 flags → 29 confirmed → 26 apply-ready + 3 rerouted.** ~0.3% convention-error
rate — confirms clean-but-convention-prone. Dominant patterns:

| Fix | n | Rule |
|---|---|---|
| `01.1.3.6.2` → `01.1.3.3.9` | 4 | surimi/crab-sticks are fish prep, not crustaceans |
| `01.1.9.9.0` → `01.1.1.9.0` | 4 | protein/corn/soy bars + crackers are cereal snacks, not the n.e.c. catch-all |
| `01.1.2.5.3` → `01.1.2.5.9` | 3 | *whole* foie gras is not pâté |
| `01.1.9.2.3` → `01.1.9.2.2` | 2 | baby rice cereal is not homogenized baby food |
| `01.1.1.9.0` → `01.1.1.1.9` | 2 | raw grain is not a milled preparation |
| `01.1.3.6.1` → `01.1.9.3.9` | 2 | bagoong (shrimp paste) is a condiment |
| singles | 9 | coffee-mate→`01.1.9.9.0`; flavored-RTD-milk→`01.1.4.7.0`; whipping cream→`01.1.4.3.3`; raw beef joint→`01.1.2.1.1`; … |

### Meta-finding: the existence guard caught Opus itself

The deterministic check against `coicop_leaves.txt` caught **3 target codes Opus
itself proposed that are not real leaves** (`01.1.1.9.9`, `01.1.4.9.9`,
`01.1.9.9.9`). A model **cannot self-catch structural invalidity**, regardless of
size — so labeler output must **always** be validated against the leaf set
downstream. The 3 were rerouted to valid neighbors (cheetos→`01.1.1.9.0`,
mongolian-white-food→`01.1.4.9.0`, meal-replace→`01.1.9.9.0`).

## Applied — reversible read-time overlay (parquets untouched)

Per the decision *"bake into the parquets only if retrain proves the gain,"* the
26+3 corrections are applied as a **read-time overlay**, not a parquet rewrite:

- `data/prices/enrich/gold/corrections/convention_audit_20260804.csv`
  (`gold_row_id, old_code, new_code, status, reason, source`).
- `dataset.py::_apply_corrections()` remaps `code` by `gold_row_id` for
  `status=='apply'` rows inside `_load_gold()`, **after** reading
  `gold_labels.parquet` and **before** deriving `division`.

Reversible (delete the CSV to undo) and survives `prices label consolidate`
(which rebuilds `gold_labels.parquet` from the gold_v5_* sources). Verified:
29/29 applied; **no leaf crosses MIN_SUPPORT** (smallest source leaf
`01.1.3.6.2` 10→6, still in the head).

## Architecture decision — accurate + token-efficient

**Two regimes, opposite economics — never conflate:**

| | Labeling gold | Classifying observations |
|---|---|---|
| Volume | ~thousands | 300k div-01 → 1.39M corpus |
| Right tool | LLM ensemble | embedding → LR head |

**The big model must never be in the hot path.** Production classification is
already accurate + near-free (embed once + LR ≈ 0); its levers are **clean gold +
tau + ensemble embedding**, not a bigger agent. Concentrate all intelligence in
low-volume gold labeling — the 300k classifications inherit the gain for free.

**Labeler levers, ranked by accuracy-per-token** (a bigger *default* model is the
worst ROID — linear cost over thousands of rows, and it does **not** fix shared
convention bias):

1. **Retrieval-grounding > bigger model** — put the official inclusion/exclusion
   note + 2–3 nearest gold exemplars in the prompt (few hundred tokens). Converts
   "guess the convention" into "apply the cited rule." (Already proved out by this
   session's note-grounded audit.)
2. **Diversity > size in the agree-gate** — keep the two labelers cheap but from
   different families; agreement only filters *independent* errors.
3. **Constrain the output space (KNN candidate-narrowing)** — hand the labeler the
   ~8–12 candidate leaves from the embedding neighbourhood instead of "pick any of
   538." More accurate **and** fewer tokens. **Agreed next step.**
4. **Escalate on signal, not uniformly** — Opus only on disagreement / low
   confidence / OOF-disagreement / audit-flags (= current skeleton, keep it).

## Wholesale channel (the one real sourcing gap) — SHIPPED

New `channel: wholesale` + two **general** fetchers (collect *all* commodities,
not just the missing leaf), verified live:

- `tw_moa_wholesale` — 4 Taiwan MOA open-data endpoints (produce + live hog +
  goat/sheep + broiler/egg), **20,881 rows**.
- `hk_afcd_wholesale` — HK AFCD daily bilingual CSV, **433 rows**.

Closes the `out_of_scope` live-animal leaves (`01.1.2.1.x`) that retail never
carries. True-zeros confirmed: `01.1.2.1.5` hares/rabbits-live, `01.1.2.1.9`
other-live; `01.3.0.0.0` is a service.

## Retrain — v16 blessed + propagated

`train-classifier --division 01 --bless` on the overlay-corrected gold → **v16
blessed** (precision 98.1% held, coverage 60.9% flat — 29 corrections/8,606 rows
cannot move an aggregate). Propagated: `classify --rebuild` → 301,172 div-01
classifications; `merge`; `build` → 1,833,898 obs (1,073,751 trusted). Parquet-
bake decision **inconclusive on coverage → overlay stays** (corrections are
correctness, not a coverage lever); no rush to bake.

## KNN-panel competence-mapping experiment — BUILT + RUN

New package `src/prices/enrich/experiments/knn_competence/` (`prep` → `panel` +
dispatched Claude agents → `analyze`). Grounded multiple-choice over KNN gold
candidates + official notes; difficulty = KNN neighbour entropy; truth = held-out
corrected gold (name-disjoint). Panel: codex `gpt-5.5`, gemini `flash-lite`,
Opus, Sonnet, 400 stratified items.

**Deterministic ceiling:** KNN reachability **92.2%** (true leaf in candidates);
free KNN-top1 baseline **77.2%**.

**Competence-vs-difficulty (accuracy-vs-truth, 8 entropy bins):**

| overall | KNN | codex gpt-5.5 | Opus | Sonnet | gemini flash-lite |
|---|---|---|---|---|---|
| | 0.772 | **0.875** | **0.873** | 0.850 | 0.828 |

- **Codex/gpt-5.5 tracks Opus across the *entire* range — no crossover**; matches
  Opus exactly (0.64) in the hardest bin. gpt-5.5 = Opus everywhere on this task.
- **Sonnet** ≈ Opus (−2.3pp), 3–6pp dips at scattered mid/tail bins.
- **Gemini-flash-lite** = Opus at entropy ≈ 0 (bins 0–1, ~25% of items, all four
  = 0.98), first dip at ~0.41 bits → Opus-level only in the low-entropy regime.
- Hardest bin caps at **0.64 even for Opus + codex** → the ceiling is retrieval /
  ambiguity (reachability), not model intelligence.

**Routing the map implies:** flash-lite for entropy ≈ 0, gpt-5.5 for the rest,
**no Opus needed**. Output: `data/prices/enrich/_experiments/knn_competence/
competence_map.csv`.

**Gotcha:** gemini free tier = rpm 15 / rpd 500 — the first unpaced run silently
returned 350/400 `code=None` (throttle, not incompetence). Fix = `rate_limit.
acquire` pacing + retry, `_done_names` retries only null rows. codex needs `-m
gpt-5.5` pinned (CLI now defaults to sol-5.6).

## Backlog

- **GROW gold** — seed ≥5 rows for the reachable-but-empty sourcing_gap leaves;
  use the now-validated note-grounding + KNN candidate-narrowing labeler.
- **Productionize the KNN-narrowed labeler** — the experiment validated the
  recipe; wire it into the gold-growth loop with entropy-routing (flash-lite ≈ 0,
  gpt-5.5 otherwise) + a downstream existence-guard so no invalid code reaches
  gold.
- **Parquet-bake** the 29 corrections (correctness call; overlay holds meanwhile).
- **Uncommitted:** `schemas.py` (+`wholesale`), 2 wholesale configs + 2 fetchers,
  `dataset.py` overlay, the `knn_competence` experiment package. Working in the
  user's checkout — not committed.
