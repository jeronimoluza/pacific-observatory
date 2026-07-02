---
name: classify-base-item-prices
description: "Loopable two-stage per-base_item COICOP classification for the prices pipeline. Stage 1 buckets every raw product name for one base_item (pineapple, rice, apple, ...) into CANDIDATE / OTHER_FORM / REVIEW / EXCLUDE via the tier-0 gazetteer + tier-1 earn cascade with a plausible_basis wrong-entity gate; stage 2 promotes CANDIDATE rows to GREEN — the earned status — only when their tier-a unit-value clears the per (base_item × pricing_basis × country) statistical gate (median ± 3·MAD, groups n≥5) and the allowed_basis soft gate. Emits an inspectable run folder data/prices/_enrich/validation_runs/{base_item}_YYYYMMDD_HHMM/ (candidates.csv + green.csv + other_form.csv + review.csv + exclude.csv + basis_conflict.txt) for human review before appending green.csv to outputs/prices/{region}_prices.csv. Use whenever the user wants to build the trusted unit-value price DB one base_item at a time — 'classify pineapple', 'run the apples/oranges workflow', 'validate CANDIDATE→GREEN for <item>', 'shrink the REVIEW pile for <item>', 'add <item> to the price DB', or references base_items.parquet / gazetteer.parquet / the validation_runs artifacts. GREEN is statistically earned, never assumed; 100% of rows stay usable (doubtful → REVIEW, never dropped). Backed by python run.py prices classify."
---

# Classify Base-Item Prices (loopable, two-stage, one base_item per run)

Productionizes the locked apples/oranges/rice methodology
(`.planning/experiments/APPLES_ORANGES_METHODS.md`). The engine lives in
`src/prices/enrich/base_items/`; this skill drives the judgment loop around the
`python run.py prices classify` CLI.

The workflow is **two-stage**: the cascade proposes CANDIDATE rows, then a
statistical gate promotes the trustworthy subset to **GREEN**. GREEN is not a
bucket you land in — it is a status you *earn*.

## Five locked principles (do not violate)

1. **Memoize the ROLE of a token, not the string** — `(base_item, token) -> role`
   converges Zipfian (gazetteer.parquet flywheel).
2. **CANDIDATE must be EARNED** via bare-item evidence, never defaulted; GREEN is
   earned a second time via the statistical gate.
3. **Basis is NOT a positive cue** — pharma has mass/count; an implausible basis
   routes to OTHER_FORM, it never grants CANDIDATE.
4. **Read the WHOLE name**, not just the base_item's neighbours.
5. **Faithfulness/provenance** — every term traces to coicop_categories.xlsx or a
   dated oracle verdict, never hand-typed.

## Buckets (100% usable — nothing is dropped)

- **CANDIDATE** — earned bare base_item that passed the `plausible_basis` gate;
  the promotable bucket. Its rows carry a tier-a unit-value and are the input to
  the GREEN gate.
- **OTHER_FORM** — processed form (juice/flour/noodle) or a physically-impossible
  basis; rerouted to another COICOP leaf.
- **REVIEW** — doubtful (brand/origin residue, unknown modifier); the flywheel target.
- **EXCLUDE** — nonfood / different-species / health-household leak.

Expected shape: **CANDIDATE is the SMALLEST bucket**; REVIEW + (OTHER_FORM|EXCLUDE)
are the two largest. If CANDIDATE is large, the earn-gate is leaking — stop and fix.

## GREEN — the earned promotion status

CANDIDATE rows become **GREEN** only when their unit-value clears a robust
statistical gate, computed per **base_item × pricing_basis × country** group:

- band = `median ± 3·(1.4826·MAD)` over the group's `unit_value_usd`.
- groups with **n ≥ 5** get a band; a row inside the band is promoted
  (`promotion_status = green`), a row outside is `candidate_outlier`.
- groups with **n < 5** are held as `candidate_small_group` (not enough peers to
  trust the band yet — they earn GREEN once the group fills in a later run).

GREEN is therefore the smallest, statistically-defensible subset of CANDIDATE.
The printed `promotion:` line is the `promotion_status` value_counts, and
`GREEN=<n>` is the earned count.

## Two-level basis gate

Basis is checked twice, at two different strengths:

- **`plausible_basis`** (hard, in the cascade) — a *physically-impossible* basis
  for the entity is a wrong-entity signal: apple-by-volume, TV-by-mass →
  **OTHER_FORM**. This is a correctness gate, not a promotion gate.
- **`allowed_basis`** (soft, in promotion) — a *plausible-but-unlisted* basis
  (e.g. oranges-by-count when only mass is confirmed for the item) does not
  demote; it is surfaced as a **basis_conflict** and written to
  `basis_conflict.txt`. Resolve it by widening the item's `allowed_basis` or
  improving parsing, then re-run.

(This replaces the old "basis mismatch demotes to REVIEW" guardrail.)

## Regex flywheel (regression-safe tier-a)

Tier-a extraction changes are gated by a frozen snapshot:

```bash
python run.py prices regex-check            # diff current extraction vs snapshot
python run.py prices regex-check --bless    # accept an intended diff after review
```

A regex change is regression-safe **iff the unintended diff is empty**. When the
diff is non-empty it is written to `regex_check_diff.csv` — review it, and only
`--bless` once every changed row is intended.

## One-time setup (first run only)

```bash
# derive shared FORM/NEG lexicons from the xlsx + seed the proven base_items
python run.py prices classify rice \
  --derive-lexicons \
  --seed-config .planning/experiments/base_item_config.json
```
This writes `data/prices/{base_items,gazetteer,source_boilerplate,derived_form_lexicon,derived_neg_lexicon}.parquet`.
To grow coverage beyond the seeded entities, generate candidate base_items from
the xlsx with `prices.enrich.base_items.taxonomy.extract_candidates(nlp)` and
review them (⚠ the `SKIP_DIVS` services filter needs a COICOP check — see the
module docstring) before classifying.

Prerequisite: the deduped cache must be built at `(product_name, url)` grain —
run `python run.py prices process` (or its prepare stage) if stale.

## The loop (per base_item — worked example: pineapple)

1. **Run the iteration.**
   ```bash
   python run.py prices classify pineapple [--region <r>]
   ```
   It greps the deduped data for the singular+plural base_name, mines per-source
   boilerplate, runs the cascade (tier-0 gazetteer → tier-1 earn → plausible_basis
   gate) to produce CANDIDATE rows, then runs the GREEN statistical gate over them.

2. **Sanity gate (first stopping point).** Read the printed `distribution`,
   `promotion:` (the promotion_status counts + `GREEN=`), and `loop-status`.
   Confirm CANDIDATE is smallest and a large share landed in OTHER_FORM/EXCLUDE via
   the plausible_basis + form reroute. If a `basis_conflict:` block printed,
   inspect it before trusting the artifact.

3. **Inspect the run folder** at
   `data/prices/_enrich/validation_runs/pineapple_YYYYMMDD_HHMM/`:
   - `candidates.csv` — ALL promoted-cascade rows plus the gate columns
     `promotion_status` / `group_n` / `group_median_usd` / `band_lo` / `band_hi`.
   - `green.csv` — the earned subset (`promotion_status == green`).
   - `other_form.csv` / `review.csv` / `exclude.csv` — the other buckets.
   - `basis_conflict.txt` — present only when an allowed_basis conflict was found.

   Each candidate/GREEN row carries product name, country, **source**,
   coicop2digit_title, deep leaf code, base_item, form/variety, currency,
   original price, the raw tier-a extraction (`regex_capture` = the matched
   packaging span + pattern id, `amount_value`, `pricing_basis`, `standard_unit`,
   `count`, `multiplier`), the `unit_value_calc_str` (`price / (amount×count×mult)`),
   unit_value_local and unit_value_usd. Verify a sample of the calc strings and
   that the CANDIDATE rows really are pineapple.

4. **Shrink REVIEW (flywheel).** The run prints:
   - `REVIEW brand/variety candidates` — tokens like `sunnyphil`/`rockit` that
     ARE the base_item. Confirm them with
     `mine.confirm_varieties(base_item, [...])` (writes gazetteer.parquet); the
     next run earns them into CANDIDATE (and then GREEN if they clear the band).
   - `REVIEW cross-base_items` — OTHER base_items hiding in the pile (a pineapple
     run surfacing `juice`/`jam`). **Report these back** as new candidate rows for
     `base_items.parquet` — they mean the base_item DB is incomplete.

5. **Promote.** Once the artifact looks right, append the earned GREEN:
   ```bash
   python run.py prices classify pineapple --region <r> --append
   ```
   (appends `green.csv` to `outputs/prices/{region}_prices.csv`).

6. **Loop until the stop rule fires.** Re-run the same base_item and stop when
   either:
   - **convergence** — < 5% of rows move buckets between runs, OR
   - **ratio** — CANDIDATE ≤ 2× GREEN,

   whichever comes first. The CLI prints this as `loop-status: STOP|CONTINUE`.
   Then move to the next base_item.

## Guardrails

- **Destructive `data/`/`outputs/` ops are blocked by a PreToolUse hook** — `rm`
  is denied, `mv` asks first, creating new objects is allowed. The skill writes
  staging under `data/prices/_enrich/` and only appends to `{region}_prices.csv`;
  never hand-delete or overwrite existing files.
- An out-of-band unit-value is held as `candidate_outlier` / `candidate_small_group`,
  never deleted; an allowed_basis conflict is surfaced (basis_conflict.txt), never
  silently dropped.
- All timestamps UTC; artifacts are provenance-stamped.
- Stops at the artifact — promotion of `green.csv` to `{region}_prices.csv` is an
  explicit, human-gated `--append`.
