# 2026-07-28 — F&B pre-filter bake-off (shrink the corpus before the embed)

## Goal

The full ensemble embed of all **1,585,556 unique `product_name_original`** on a
16GB Mac takes ≈95h (4 days) — the 8B-q8 block is ~58% of that cost. But the only
current deliverable is **COICOP division 01 (food & beverages)**, which is ~22% of
the corpus. So: **pre-filter the 1.585M names down to div-01 F&B *before* embedding**,
and only embed the survivors. ETA scales linearly with pass-rate, so a good filter
turns 95h into ~1 day. Bar: keep F&B recall high (dropped food is a permanent
pre-embed loss) while shrinking the pass-rate as much as possible.

## Method — comparable bake-off

Three Sonnet agents, each a different filtering approach, scored against **one
shared gold benchmark** (`_load_gold()` `code` col → `is_fb = code[:2]=="01"`;
8,272 F&B / 6,093 non-F&B; 14,365 rows). Identical scorecard so the approaches
differ only in method. Corpus signal columns available: `product_name_original`
(the only reliable one), `category` (76.7% populated but 192k distinct, multilingual,
opaque), `channel` (100%), `source`. Dead signals confirmed: `lang` (uniformly
'en', useless), `declared_coicop_codes` (0.7% populated, all rent 04.1.1).

## Result — Approach C (char n-gram + LogisticRegression) WINS

**`HashingVectorizer(analyzer="char_wb", ngram_range=(2,5), n_features=2^20)` +
`LogisticRegression(C=10)`, name-only.**

- Threshold **0.3299** → **98.0% gold recall**, **24.04% corpus pass-rate**
  (381,228 of 1.585M names) → ETA ≈ 0.24 × 95h ≈ **22.8h (4.2× cut)**.
- Scores the whole corpus in ~56s. Pass-rate ≈ the known 22.4% food fraction
  (`prices_food_fraction_result_20260714`) — good calibration.
- **Why it wins:** char n-grams are the only **language-agnostic learned** signal.
  The corpus is **CJK-majority** (65.5% of unique names = Han 727k + kana 311k;
  Latin only ~31%), so anything that needs words or a category string fails where
  the mass is.
- Adding metadata (channel one-hot) was negligible. Systematic false positive =
  alcohol (div-02) — a safe keyword veto would lift precision without touching
  div-01 recall.

**Approach A (metadata priors: category/source/channel) — weak solo.** 76% pass @
98.8% recall → 72h (only 24% cut). Root cause: **69% of unique names have no usable
`category`** (23% empty + 46% opaque), so recall-protection forces keeping that mass.
Category classifier is near-perfect *where* a real dept string exists (~11%) — so it's
useful as a **complement to rescue C's misses**, not as a solo filter.

**Approach B (multilingual name lexicon) — not viable.** 93.5% recall (misses the
bar), 37% pass. Structural ceiling: keyword lexicons cap ~74–77% recall on
CJK/kana/Korean, which is exactly where the corpus mass sits. Latin slice is fine
(97%). Confirms the long-standing "CJK/kana weak, Thai/Cyrillic dead" finding.

## Validation — the 98% is a gold number, real recall is ~93%

Gold is F&B-enriched (58% F&B) and not corpus-representative, so gold recall can
overstate real recall. To measure directly, hand-judged **200 random *rejected*
corpus names** (`random_state=42`; rejected side is 47.8% JP-kana / 25.7% Han / 25%
Latin):

- **3 clear + 1 borderline** real div-01 food wrongly rejected (~1.75% of the
  rejected side): Foody Sturgeon Stew (proba 0.11), Knorr chicken broth
  家樂牌純鮮清雞湯 6×250ml (0.25), Otafuku okonomi/nanban sauce pouch set (0.29),
  Coppa 750ml coconut (0.14, borderline). Everything else was genuinely non-food
  (home goods, apparel, cosmetics, toys, books) or correctly-excluded
  alcohol/tobacco/supplements/pet/restaurant listings.
- Rejected side 1,204,328 × ~1.75% ≈ **~21k real food dropped**; passed food ≈274k
  → **real corpus recall ≈ 93% (91–94% range), NOT the 98% gold figure** — gold
  overstates ~5pp from distribution shift. n=200 is coarse (95% CI on recall ≈
  88–97%); a 500–1000 sample would tighten it.
- **All 4 false negatives are short packaged-grocery names just below τ=0.33**
  (proba 0.11–0.29), all from `wellcome_hk` / `citymall_mm` grocery. Reclaim
  options: lower τ (0.20 → 35% pass / 33h catches broth+sauce; 0.10 → 48% / 45h
  catches stew) **or** a cheaper **targeted metadata rescue** = union C with
  grocery-channel + food-category items scoring *below* threshold. So 22.8h is real,
  but the recall/speed knob is the open decision.

## Artifacts (job-scoped `tmp/`, ephemeral — regenerate from `train.py`/`score_corpus.py`)

- `agentC_corpus_scored.parquet` — all 1.585M names + `fb_proba`/`fb_pred`; any
  threshold applies instantly to `fb_proba`.
- `agentC_model.joblib` (183MB) — vectorizer + LR + threshold bundle.
- `fb_benchmark.parquet` — the shared gold benchmark.
- `agentC_train.py`, `agentC_score_corpus.py`, plus `agentA_*`/`agentB_*` and the
  hand-judged `rejected_sample_200.csv`.

Full detail in memory `prices_fnb_prefilter_bakeoff_20260728`.

## Next session (plan locked with the user)

1. **Integrate the F&B filter into the pipeline** (exact wiring TBD) — the char-ngram
   LR runs after `prepare`, before the embed, so the embed only sees passing food.
2. **Embed the passing food in resumable, shared batches** — reuse the block-outer
   driver (`classifier/batch_embed.py`, one model at a time, stream to disk,
   `run_key` resume) so an interrupted run continues.
3. **Store the word vectors in float16** — halve the on-disk footprint of the 7680-d
   ensemble embeddings.

Open decision carried in: **operating threshold** (accept τ=0.33 ≈93% recall/22.8h,
or trade speed for recall via lower τ / the metadata rescue).

## Notes / gotchas

- The **full 1.585M-corpus embed remains HELD** — not launched this session.
- Work done **in place** (worktrees off convention; `src/prices/` doesn't exist on
  `main`, `template-repo` is far ahead of `origin/main`).
- Prior-session uncommitted source edits still present, untouched this session:
  `config.py` (4B/8B seq 512→176) and `embedding_mlx.py` (length-sort in `_embed`) —
  a separate ~3.6× MLX wall-clock speedup lever, not part of this filter work.
