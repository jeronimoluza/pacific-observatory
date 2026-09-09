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

| stage | cells | share |
|---|---|---|
| No candidate - model never proposes that leaf in that country | 1,203 | 49.6% |
| Classifier-blocked - candidates exist, zero accepted | 462 | 19.0% |
| Accepted but never published | 761 | 31.4% |

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

`outputs/label_pack_gapfill_<date>.csv` - 8,354 rows over all 28 countries and 26
COICOP families, addressing 603 of the 689 classifier-limited gap cells (38 leaves).
Two sources: `uncertainty` (2,283 rows - model proposed the exact target leaf but
rejected it) and `sibling` (6,071 rows - model landed in the target leaf's parent
family). Stratified at 30 rows per (country, family) and 450 per country so no
country or family dominates; scripts are latin 6,126 / cjk 1,151 / hangul 437 /
cyrillic 362 / thai 199.
