"""Gold evaluation harness for the prices enrichment cascade.

First-class home (promoted out of `tests/`) for scoring the 3-tier cascade
against the working gold set at `data/prices/enrich/gold/gold_labels.parquet`
(313 rows: 300 oracle + 13 human-overridden, split by provenance from the
legacy set; the 187-row held-out certification set is reserved for milestone close).

Beyond per-field accuracy it grades the composed `unit_value` and attributes
every miss to one of three causal buckets:

    A_coicop     wrong COICOP leaf
    B_basis      right COICOP, wrong pricing_basis
    C_magnitude  right basis, wrong unit_value magnitude

Entry point: `prices.enrich.eval.runner.run()` (also `python run.py prices eval`).
"""

from prices.enrich.eval.runner import run

__all__ = ["run"]
