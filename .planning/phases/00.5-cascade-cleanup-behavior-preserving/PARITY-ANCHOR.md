# Phase 0.5 Parity Anchor — the BEFORE baseline (D-09)

The fixed before-half of the D-08 behavior-preserving guardrail. Every cleanup
commit in plans 02–06 reruns `poetry run python run.py prices eval --no-write`
against the same 313-row working gold and must reproduce the per-dimension
**Overall accuracy** table below byte-for-byte. A non-matching after-number blocks
the commit.

## Run conditions

| field | value |
|---|---|
| captured (UTC) | 2026-06-18 18:05 UTC |
| commit SHA | `48b1a7501fd3563c8c28b81e1156da0e6ba4bf8e` |
| gold path | `data/prices/enrich/gold/gold_labels.parquet` |
| n_total (rows) | **313** (de-contaminated working gold: 300 oracle + 13 human-overridden) |
| cache scanned | 41,503 rows |
| tier-c | **OFF** (deterministic baseline, no LLM calls) |
| harness | `poetry run python run.py prices eval --no-write` (writes nothing under `outputs/`) |

## Per-dimension Overall accuracy (the parity table)

| metric | correct | total | accuracy |
|---|---|---|---|
| coicop_code | 73 | 313 | **23.32%** |
| sub_label_id | 9 | 313 | 2.88% |
| pricing_basis | 287 | 313 | 91.69% |
| standard_unit | 287 | 313 | 91.69% |
| unit_value | 281 | 313 | **89.78%** |

## Causal buckets (supporting context, not part of the parity gate)

| bucket | count | share |
|---|---|---|
| A_coicop (wrong COICOP leaf) | 240 | 76.68% |
| B_basis (right COICOP, wrong pricing_basis) | 11 | 3.51% |
| C_magnitude (right basis, wrong unit_value) | 4 | 1.28% |
| ok | 58 | 18.53% |

Residual rows (tier-b → tier-c): **197** — `miss:below_hard_cos` (193, 97.97%),
`post_accept_veto` (4, 2.03%). With tier-c off these score 0% on coicop/sub_label,
which is what caps overall coicop at ~23%.

## Delta vs Phase 0 BASELINE.md

| field | BASELINE.md | this anchor | delta |
|---|---|---|---|
| commit SHA | `99c18a88` | `48b1a750` | +1 commit ahead |
| coicop_code | 73/313 (23.32%) | 73/313 (23.32%) | none |
| sub_label_id | 9/313 (2.88%) | 9/313 (2.88%) | none |
| pricing_basis | 287/313 (91.69%) | 287/313 (91.69%) | none |
| standard_unit | 287/313 (91.69%) | 287/313 (91.69%) | none |
| unit_value | 281/313 (89.78%) | 281/313 (89.78%) | none |

**Cause of the SHA difference, eval numbers identical:** HEAD is exactly one commit
ahead of BASELINE.md's `99c18a88`. The intervening commit is
`48b1a750 chore(prices/enrich): checkpoint uncommitted working state before phase 0.5 cleanup`
— a working-state checkpoint that did not alter any cascade decision path, so the
per-dimension Overall accuracy reproduces BASELINE.md exactly. This anchor's SHA
(`48b1a750`), not `99c18a88`, is the correct before-point for plans 02–06 because it
is the actual tree state cleanup begins from.

## Reproduce

```bash
poetry run python run.py prices eval --no-write   # prints this scorecard, writes nothing
```

Persisting the canonical report under `outputs/prices/reports/eval/` (run without
`--no-write`) is left as a user action per CLAUDE.md data-safety (`outputs/` is
user-handled).
