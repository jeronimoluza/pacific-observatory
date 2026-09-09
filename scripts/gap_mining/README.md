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
| `a_split.py`         | is a gap leaf model-blind, or just absent in that country? |
| `corr.py` `causal.py`| does gold count predict coverage? controlled for candidate volume |
| `prio.py`            | select label-addressable / classifier-limited target leaves |
| `extract.py`         | uncertainty sampling: rejected rows already proposed as the target leaf |
| `lex2.py` `spot.py`  | lexical sweep + spot check. REJECTED - CJK substring precision too low |
| `sib.py`             | sibling mining: right parent family, wrong/rejected leaf (language-agnostic) |
| `pack.py`            | assemble the stratified label pack CSV |

Outputs land in `outputs/` (gitignored, lives on the Geekom).

## Headline findings

- 5,348 addressable leaf x country cells; 2,426 (45%) are gaps.
- Gaps die in three places: 49.6% never get a candidate, 19.0% are classifier-blocked,
  31.4% are accepted but never published (70% of those killed by QA, 17% stale >60d).
- Gold labels per leaf predict matrix gap rate at Spearman -0.888.
- Controlled for candidate volume, labels only convert to coverage in a middle band
  (~600-2,300 candidates/leaf). Below it the cell is supply-limited; above it saturated.
- Naive multilingual term matching does NOT work on CJK product names.
