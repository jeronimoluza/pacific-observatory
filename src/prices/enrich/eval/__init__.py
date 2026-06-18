"""Gold evaluation harness for the prices enrichment cascade.

First-class home (promoted out of `tests/`) for scoring the 3-tier cascade
against the consolidated gold set at `data/prices/_enrich/gold_labels.parquet`
(500 rows: gold_v3_curated + codex + opus-4.7, all treated as ground truth).

Beyond per-field accuracy it grades the composed `unit_value` and attributes
every miss to one of three causal buckets:

    A_coicop     wrong COICOP leaf
    B_basis      right COICOP, wrong pricing_basis
    C_magnitude  right basis, wrong unit_value magnitude

Entry point: `prices.enrich.eval.runner.run()` (also `python run.py prices eval`).
"""

from prices.enrich.eval.runner import run

__all__ = ["run"]
