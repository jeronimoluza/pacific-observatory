# 2026-07-30 — Upstream parsing fixes (from the 3-lens consumable audit)

## Goal

Record every upstream parsing/extraction defect the Opus 4.8 unit-value audit
surfaced against the 4 consumable deliverables
([[2026-07-29-classify-and-downstream-exploration]] built the classify; the
consumable prototype lives in job-tmp `build_consumable.py`, not yet a module),
so a later session can fix them at the source in `src/prices/enrich/`. Also
quantifies what the consumable parquets lose if we exclude parsing errors +
aggregators.

> **UPDATE (later 2026-07-30 session): F1, F4, F5, F6 IMPLEMENTED + verified
> end-to-end in `data/prices/build/`.** F2, F3, F7 deferred (rationale below).
> See **"## Implemented + verified"** at the bottom.

The audit's structural verdict first: **the 4 consumable files are internally
coherent — the prototype math is correct.** Every cross-file check passed exactly
(products.median vs its observations 0/10,000 mismatches; snapshot.latest vs
last-day observation 0/10,000; summary monthly medians vs observations 0/36,212).
**Every defect below is upstream in `src/prices/enrich/` parsing/extraction**,
inherited by the build input — none is a bug in the consumable build itself.

## The fix-list

| # | Bug | Blast radius | Root cause | Fix location |
|---|---|---|---|---|
| **F1** | VND prices ~1,000× too low | 155/273 VND obs rows (57%) | `parse_price` dot-thousands set omits VND → "10.000₫" parses as `10.0` | `enrich/stages/prepare.py:16-19` — add `VND` to the dot-thousands currency set. **One-line, highest impact-per-effort.** |
| **F2** | IDR unit values $5k–$16.6M/unit | 9 products | corrupt raw price strings (digit concat in the scrape) | upstream scrape / `parse_price` sanity bound; or a `price_local` upper-sanity gate in QA |
| **F3** | mg/sachet dose read as net weight | 15 clear (supplements → $18k–$48k/kg) | per-unit pharma guard (`extract._PHARMA_PER_UNIT_RE`) misses sachet / Cyrillic `№` / `500mg` strength | `enrich/extract.py` — extend guard to strength/dose tokens; separate dose from net weight |
| **F4** | multipack pack count lost → per-kg inflated 20–100× | 17 confident / 169 candidate (Korea/SG/Myanmar) | `extract_decide` routes `"1.5g × 20개"` pack into `count` (UV-inert under Convention A) instead of `multiplier` | `enrich/extract_patterns.py` / `extract_decide` — for mass/volume basis, route `"V unit × N counter"` into `multiplier` |
| **F5** | "Per KG" products lose UV entirely (NaN) | 26 products / 430 obs | mass basis + NaN `amount_value` → `compute_unit_value` returns None | `enrich/extract.py` set `amount_value=1` for "Per KG/Per L" names; or handle NaN-amount mass in `build/merge.compute_unit_value:51` |
| **F6** | $0 prices shipped as trusted | 112 rows / 11 products | out-of-stock scrapes; `0.0` is a valid float, slips every gate | add `price_local > 0` gate to the trusted filter (`build/qa.py`) — also fixes downstream regardless of upstream |
| **F7** | one stale MNT FX rate | 1 row | isolated stale pin | `build/fx.py` refresh; FX otherwise sound |

**Priority (impact-per-effort):** F1 (one line, fixes 57% of a country) → F6 (one
gate, purely additive) → F4 (pack routing) → F3/F5 (dose-vs-weight + Per-KG amount).
F2/F7 are 1–9 rows, low urgency.

**Convention reminder (do not "fix" this):** `merge.compute_unit_value:51`
Convention A — for mass/volume basis, `count` is unit-value-inert; only
`multiplier` scales the denominator. F4 is a bug *because* the pack qty lands in the
inert `count` field; the fix is to route it to `multiplier`, not to change the
convention.

**Prototype-side guard (DONE this session, downstream — independent of upstream).**
`build_consumable.py` now (a) excludes the 3 aggregator sources
(`AGGREGATOR_SOURCES = {livingcost, expatistan, mylifeelsewhere}`) in
`load_trusted()`, dropping the 13 sole-aggregator countries, and (b) keeps only
positive unit values — a `unit_value_local > 0` filter in `daily_series()` (drops
F5 NaN "Per KG" + F6 $0 daily rows so the observations file is clean), reinforced
by a `median_unit_value_local > 0` guard in `allocate()`. Rebuilt: **10,000
products (re-filled from real retail) / 24 countries / 173 leaves**; 0 aggregators,
0 non-positive/NaN unit values in any of the 4 files, cross-file coherence
preserved (0 median mismatches). Aggregators to be revisited later. These are
downstream cleaning steps — the F1–F7 upstream fixes above are still pending.

## Exclusion analysis — "if we drop parsing errors + aggregators, what do we lose?"

**Aggregators** = the 3 multi-country crowd-sourced USD-basket sources:
`livingcost` (356 products / 30 countries), `expatistan` (51 / 12),
`mylifeelsewhere` (23 / 9) = **430 products (4.3%)**. Everything else is
single-country real retail.

**Key distinction:** parsing errors should be **fixed, not dropped** — they're
recoverable (F1 VND is just ÷1000). Dropping instead of fixing needlessly kills
Vietnam (all 35 VND products). So the honest "exclude" scenario is
**aggregators-dropped, parse-errors-fixed**:

| metric | before | after (drop aggregators) | kept |
|---|---|---|---|
| products | 10,000 | 9,570 | 95.7% |
| countries | 37 | 24 | −13 |
| **COICOP leaves** | **173** | **173** | **100%** |
| observations | 191,730 | 174,668 | 91.1% |
| unit_value_summary (product-months) | 36,212 | 30,503 | 84.2% |
| latest_snapshot | 10,000 | 9,570 | 95.7% |

**The 13 lost countries are exactly the 13 where an aggregator is the SOLE
source** — China, Kiribati, DPR Korea, Marshall Is., Palau, Solomon Is., Tuvalu
(livingcost @13 products each); French Polynesia, Guam, Macao, New Caledonia,
N. Mariana Is., Micronesia (expatistan/mylifeelsewhere @8–9 each). Each is a fixed
~9–13-item USD basket with **one snapshot and no real price time series** — the
5-agent synthesis and both economics agents already flagged these as **0 usable
(leaf,country) cells** (thin-cell, USD-only). The 24 real-retail countries lose
only their aggregator rows and keep all genuine retail.

**Verdict: excluding aggregators makes the dataset *better* for downstream
analysis, not worse.** We lose the analytically weakest 4.3% (a crowd USD basket in
countries that were never usable), **zero COICOP-leaf coverage**, and we remove the
currency-composition FX artifacts the audit root-caused (Myanmar USD→MMK, Lao PDR
monthly alternation) plus the single-source PPP-inversion noise. Parsing errors are
a rounding error either way — ~66 products by robust heuristic, ~149 (~1.5%) by the
audit's fuller estimate — and are fixable, not lossy.

**Recommended downstream policy:** ship a `source_class ∈ {retail, aggregator}`
column rather than hard-dropping — aggregators are still the *only* signal for those
13 countries, so a consumer doing cross-country PPP can opt in, while a consumer
doing real price series filters `source_class=='retail'`. Pair with the
`price_local > 0 & unit_value notna` guard (F5/F6).

## Next session

Implement the fixes lowest-risk first: **F1** (one line) + **F6** (one gate) +
the prototype `allocate()` guard → re-run the consumable build → re-audit. Then
**F4**, then **F3/F5**. Fold the `source_class` column into the consumable
promotion (`src/prices/build/consumable.py` — still a job-tmp prototype). The
upstream `canonical_product_id` refinement (mining size tokens from URL slugs to
protect the ~0.3%/27 real-variant groups) remains its own separate session.

## Implemented + verified (later 2026-07-30 session)

Dispatched Sonnet agents for the fixes, then verified end-to-end against
`data/prices/build/` (NOT the consumable prototype — the user asked to verify
"the one after build"). Baseline captured from the pre-fix build outputs.

### Source changes (4 fixes)

| Fix | File | Change |
|---|---|---|
| **F1** | `enrich/stages/prepare.py:13` | added `"VND"` to `_EU_FORMAT_CURRENCIES` (dot = thousands) |
| **F5** | `enrich/extract_decide.py` `_rung_basis_marker_emit` | bare "Per KG"/"Per L" now emits `amount_value=1.0` (was `None` → UV dropped) |
| **F4** | `enrich/extract_decide.py` `_rung_pack_unit_emit` + new `_MULTIPLY_OP_ADJ_RE` | a per-unit-measure joined to a counter by an explicit `×`/`x`/`X`/`✕`/`*` operator ("1.5g × 20개", "90g*3개입") now routes the counter to `multiplier` (was the UV-inert `count`); `_is_total_breakdown` + "500g (6 pieces)" totals unchanged |
| **F6** | `build/qa.py` | new `qa_price_positive` gate → `price_local<=0`/NaN quarantined as `review_zero_price` (checked first) |

### Refresh method — surgical, NOT `--stage classify --rebuild`

**Critical gotcha discovered:** a plain `prices process --stage classify --rebuild`
would have **silently reverted the phase-0 alcohol veto** — it reuses the stale
Jul-29 `_classify_pred/v11/` shards (which predate the Jul-30 veto), re-accepting
the ~132 alcohol rows. The veto is applied *behind* the pred-shard cache, so it
only re-fires on a forced re-score. Also the 6.2 GB embed store is fully banked,
so no path needs a re-embed.

So structural fields were refreshed **surgically** (job-tmp
`surgical_refresh_structural.py`): join `classified.parquet` ↔ `products_input`
on `input_hash`, recompute `classify._structural_fields` (= `extract()`) on the
187,306 unique names, overwrite ONLY the 9 structural columns, leave
`coicop_code`/`confidence`/`state` byte-identical (asserted). Within scope: 199
`amount_value` (F5) + 506 `count`/`multiplier`/`is_multipack` (F4) rows changed,
**0 `pricing_basis` changes** (so the basis-audit → `trust_level` coupling is
invariant — no re-audit needed). Post-write: 224,320 rows, soft-drinks
`01.2.6.0.0` = 11,662 (veto intact). Backup: `classified.parquet.bak-*`.

Sequence (≈15 min, no re-embed): surgical overwrite →
`prices process --stage prepare --rebuild` (F1 VND for the snapshot;
`_invalidate_for("prepare")` only unlinks `products_input`, no cascade) →
`prices build`.

### Verification vs baseline (trusted / `eap_fnb_observations.parquet`)

| Fix | Baseline | After | Verdict |
|---|---|---|---|
| **F6** | 194 trusted `price_local<=0` | **0** (341 obs → `review_zero_price`) | ✅ clean |
| **F5** | 984 per-kg rows, NaN `amount_value`/UV | **0 NaN UV**; 1,182 at `amount_value=1.0`; 1,783 with real UV | ✅ clean |
| **F1** | ~2,399 VND trusted at `uv_usd≈0.002` | **0** below 0.01; VND median `uv_usd` $22.8, values $7–50/kg | ✅ (trusted VND 3,688→1,385: corrected tail now trips the uv-outlier gate) |
| **F4** | KR/SG/MM multipacks with count-inert inflation | **arithmetic match 1.0** on 1,637 KR rows: `uv = price/(amount×multiplier)`; each value now `multiplier`× lower | ✅ (`uv_usd>50` rose 1,195→1,621 because corrected rows now *pass* QA; residual highs are genuine dry goods) |

Total trusted: 759,901 → 759,303. New status `review_zero_price` = 341.

### Deferred (with rationale)

- **F2** (implausibly-high `uv_usd`): the 1,427 trusted `>1000` rows are mostly
  **legit premium goods** (NZD/NZ 299, USD/Cambodia 392, KRW 258; IDR only 39) —
  a blanket cap kills real data. Needs a per-currency corrupt-string sanity
  bound, not a UV cap.
- **F3** (dose-as-weight): ~15 rows with genuine bare-`mg` net-weight-vs-strength
  ambiguity — high regression risk, tiny payoff.
- **F7** (stale MNT FX): 1 row; needs a live FX refresh.

### Not done (out of scope by request)

The **consumable datasets** (`outputs/prices/consumable_datasets/` +
`data/prices/build/consumable/`) were NOT regenerated — the user scoped
verification to the post-build tables. They are now stale w.r.t. F1/F4/F5/F6 and
should be rebuilt (job-tmp `build_consumable.py`) when promoted.

### Tests

`tests/prices/enrich/test_extract*` + `tests/prices/build/` → **130 passed**.
The F6 gate needed one tweak for the existing minimal test fixtures: read
`price_local` via `df.get("price_local", pd.Series(1.0, index=df.index))` (a
missing column defaults to positive/pass) — mirrors how `qa_fx`/`trust_level`
already use `df.get` in `qa.py`; real finalize frames always carry `price_local`
so the verified behavior is unchanged. One pre-existing unrelated failure:
`test_prepare_dedups_on_input_hash` (stale expected hash — fails identically with
F1 stashed). The retired-cascade test modules (`test_tier_c`, `test_dedupe`,
`test_taxonomy_validity`, `test_cache_migration`) error at collection as before.

### Not committed

Source edits (`prepare.py`, `extract_decide.py`, `qa.py`) are unstaged in the
user's checkout (worktrees off — data-dependent build). `qa.py` is untracked.
Awaiting user go before commit.

## Next session

- Commit F1/F4/F5/F6 (source only) on user go; add a regression test for the
  F4 `×`-operator routing and the F6 zero-price gate.
- Regenerate the consumable datasets against the fixed build; fold the
  `source_class` column in during the `src/prices/build/consumable.py` promotion.
- F2 (per-currency corrupt-string bound), then F3/F7 if worth it.
- The upstream `canonical_product_id` refinement (mining size tokens from URL
  slugs) remains its own separate session.

## Artifacts

- Source: `enrich/stages/prepare.py`, `enrich/extract_decide.py`,
  `build/qa.py` (unstaged).
- Data (rebuilt): `data/prices/enrich/cache/classified.parquet` (F4/F5 structural
  overlay; veto preserved; backup alongside), `data/prices/enrich/products_input.parquet`
  (F1 VND), `data/prices/build/eap_fnb_*.parquet` (F1/F4/F5/F6).
- Job-tmp scripts: `surgical_refresh_structural.py`, `verify_fixes.py`.
