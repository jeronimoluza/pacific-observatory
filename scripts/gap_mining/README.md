# Gap mining: top-down COICOP x country coverage analysis

Works backwards from the EAP coverage matrix (`template-repo/inputs/EAP_Matrix(Sheet1).csv`)
to find which weak cells are addressable by more training labels, and to mine the
unlabeled pool for candidates in exactly those cells.

Run order:

| script | what it does |
|---|---|
| `m1.py m2.py m3.py`  | decode the matrix: depth structure, per-country / per-leaf gap profile |
| `agg.py`             | one pass over 256 hierlex pred shards -> leaf x country x score-band census |
| `triage.py`          | join matrix gaps to candidate supply + gold counts; bucket A/B/C |
| `cver2.py`           | verify buckets against published observations (QA vs 60d staleness) |
| `tau95.py`           | re-derive the triage at the shipped target_95 tau |
| `qa.py`              | which QA gate kills the cells that have observations but none trusted |
| `a_split.py`         | is a gap leaf model-blind, or just absent in that country? |
| `corr.py` `causal.py`| does gold count predict coverage? controlled for candidate volume |
| `prio.py`            | select label-addressable / classifier-limited target leaves |
| `extract.py`         | uncertainty sampling: rejected rows already proposed as the target leaf |
| `lex2.py` `spot.py`  | lexical sweep + spot check. REJECTED - CJK substring precision too low |
| `sib.py`             | sibling mining: right parent family, wrong/rejected leaf (language-agnostic) |
| `pack2.py` `spot2.py`| assemble and spot-check the stratified label pack |

Outputs land in `outputs/` (gitignored, lives on the Geekom).

## Headline findings

**Scale.** 5,348 addressable leaf x country cells; 2,426 (45%) are gaps. Verified: all
2,922 filled cells have a recent trusted observation, only 22 gaps do.

**Where the gaps die.**

Measured at the frozen `accepted` column (old tau 0.9437) and re-derived from the score
bands at the **shipped `target_95` tau 0.5893**:

| stage | old tau | shipped target_95 |
|---|---|---|
| A - no candidate; model never proposes that leaf in that country | 1,203 (49.6%) | 1,203 (49.6%) |
| B - classifier-blocked; candidates exist, zero accepted | 462 (19.0%) | **154 (6.3%)** |
| C - accepted but never published | 761 (31.4%) | **1,069 (44.1%)** |

The tau change alone unblocks 283 cells. Band-derived old-tau counts differ from the
frozen column by ~25 cells because the 0.9376-0.9437 band straddles the old threshold.

By terminal cause against the published observations: 71.6% never became an observation
row, 22.1% have observations that all fail QA, 5.4% are trusted but older than the 60-day
window, 0.9% are actually present (matrix staleness).

**The QA-killed cells are a quantity-parser problem, not a classifier problem.**
Of 45,136 observations in those 536 cells, 81.4% carry `review_missing_qty` and
18.2% `review_uv_thin`. Nothing there is fixed by more labels.

**Gold labels predict coverage at Spearman -0.888.** Bottom decile (median 12 labels)
-> 89.8% gap rate; top decile (median 2,564) -> 7.0%. Fully-covered leaves carry a
median 528 gold labels; the 40 worst carry 18.

**But labels only convert to coverage in a middle band of candidate supply.**
Holding candidate volume fixed:

| candidate volume | low-gold acceptance | high-gold acceptance |
|---|---|---|
| Q1 (~111)    | 48.1% | 49.1% (no effect - supply-limited) |
| Q2 (~692)    | 37.1% | 60.7% |
| Q3 (~1,809)  | 37.7% | 64.1% |
| Q4 (~11,718) | 55.2% | 52.6% (no effect - saturated) |

**Naive multilingual term matching does NOT work on CJK product names.** A 29-leaf
term sweep returned 94,398 hits whose spot-check was dominated by false positives:
`小米` (millet) matched Xiaomi phones, `タラ` (cod) matched イッタラ (Iittala tableware),
`감` (persimmon) matched 감귤/감청/안감, `小麦` (wheat) matched 小麦粉 and 小麦肌.
Superseded by sibling mining, which is language-agnostic and needs no term lists.

## The label pack

`outputs/label_pack_gapfill_<date>.csv` - 6,726 rows over all 28 countries and 26
COICOP families, addressing 571 of the 689 classifier-limited gap cells (38 leaves).
Every row is still rejected under the shipped `target_95` tau and is ranked by
distance to that decision boundary.

Two sources: `uncertainty` (1,519 rows - model proposed the exact target leaf but
rejected it) and `sibling` (5,207 rows - model landed in the target leaf's parent
family). Stratified at 30 rows per (country, family) and 450 per country so no
country or family dominates; scripts are latin 4,790 / cjk 893 / hangul 438 /
cyrillic 340 / thai 168 / other 96.

Spot-checked clean: Fiji "SEALORD HOKI FILLETS" against the gadiform leaf, Samoa
"Fish (Vaisu)", Mongolia "Шөл аягатай далайн байцаатай" (seaweed soup), Japan
海ぶどう (sea grapes) at score 0.49 against the seaweed leaf.

---

# World run (2026-09-09)

Same method, whole world. The matrix comes out of the shipped dashboard rather
than a hand-exported CSV: `gmx.py` brace-matches `const DATA = {...}` out of
`outputs/prices/global_prices_dashboard.html`, so the triage is against exactly
the cells Will sees.

## Universe

195 deep COICOP leaves (depth 5, plus depth-4 leaves with no depth-5 child,
minus the 53 residual `n.e.c.` catch-alls) x 209 countries = **40,755
addressable cells, 14,173 filled (34.8%), 26,582 gaps.**

## Triage at the shipped target_95 tau (0.5893)

| bucket | cells | share | EAP for comparison |
|---|---|---|---|
| A - model never proposes that leaf in that country | 14,843 | 55.8% | 49.6% |
| B - candidates exist, zero accepted | 1,616 | 6.1% | 6.3% |
| C - accepted, never published | 10,123 | 38.1% | 44.1% |

The proportions barely move between EAP and the world, which is the useful
result: the shape of the coverage problem is not regional.

## What does not transfer

The EAP target rule (`gaps>=8 & gold<250 & cand>=200 & acc_rate<0.45`) selects
**4 leaves** at world scale. Leaf-global acceptance worldwide runs 0.70-0.83
because the pool is dominated by high-resource countries, so a leaf that is
badly broken in Mongolia looks healthy in the global average. **The binding
constraint at world scale is per-cell, not per-leaf**, and targeting had to move
to the cell.

The world causal test also comes out weaker than EAP's (Q2 rho=0.269 p=0.062,
Q3 rho=0.245 p=0.093, Q1/Q4 flat). Same middle-band shape, less signal - the
world leaf set is more saturated.

## Three failure modes, only two of them ours

`gw8.py` classifies every deep leaf by how its coverage fails:

| mode | leaves | median fill | median cand | median gold | verdict |
|---|---|---|---|---|---|
| suppressed | 51 | 13.4% | 1,259 | 44 | **label these** |
| patchy | 110 | 52.4% | 8,403 | 293 | label the anomalous blanks |
| no_supply | 34 | 4.3% | 263 | 16 | **new specialised sources** |

`no_supply` is the answer to Will's second approach and is a separate file:
live poultry, live pigs, fresh dates, fresh beans, cassava leaves, quinoa flour,
yams, sorghum, pigeon peas, cocoa beans, beet sugar. Fewer than 500 candidates
each across 32.7M predictions - these are not sold on the sites we scrape.

A gap on a `patchy` leaf is only mined when it is *anomalous*: the leaf is
published for >=25% of the countries in the same region, so the blank is a
pipeline failure rather than a fact about the market. Without that filter the
pool fills with garbage - every French steak tagged against "Meat of horses",
every peach against "Tunas" - because sibling mining will happily assign a whole
family to a leaf the market does not stock.

## Pack

`outputs/label_pack_world_20260909.csv` - **47,389 rows, 205 countries, 59
COICOP families**, covering 4,508 of the 5,119 in-scope cells.

Two changes from the EAP pack:

1. **The sibling explode is collapsed.** One row per (product, country, parent
   family), listing every missing sibling leaf in `candidate_for`. Exploding one
   product across three missing siblings made it consume three labelling slots
   for one label.
2. **Score floor 0.15.** Below that the model is confidently placing the row
   somewhere else and the row is not a near miss.

Caps: 60 per (country, family), 1,200 per country, ranked by source then
proximity to the tau boundary. Nauru-to-Israel spread is 1 to 1,175.

Split for the handoff into two strata-balanced halves (alternating within each
country x family stratum, max per-country imbalance 20 rows):
`..._half_A_internal.csv` (24,458) and `..._half_B_william.csv` (22,931).

## Run order

| script | does |
|---|---|
| `gmx.py` | pull `DATA.current` out of the dashboard HTML |
| `gw1.py` | world universe + A/B/C triage |
| `gw2.py` | leaf profile, gold correlation, causal band |
| `gw3.py` | `(country, parent_pred, band)` census over the 256 shards |
| `gw4.py` | sibling reachability of every gap |
| `gw7.py` | anomalous vs structural split + sourcing brief |
| `gw8.py` | leaf failure modes |
| `gw5.py` | mine the candidate pool |
| `gw9.py` | scope the pool to label-addressable cells |
| `gw10.py` | build the pack |
| `gw11.py` | spot-check |
| `gw12.py` | split into halves |
| `enrich_pack.py` | attach retailer context from `products_input` |
| `mkbatches.py` | pack -> `gold_v5_batch_*.csv` labeling batches |
