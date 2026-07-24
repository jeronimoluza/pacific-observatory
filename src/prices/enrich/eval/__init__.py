"""Gold evaluation for the (embedding -> head) COICOP classifier.

Scores the logistic-regression head against the canonical gold set
(`data/prices/enrich/gold/gold_v5_8k_final.parquet` + rounds + fnb_extra) using
5-fold out-of-fold predictions, reporting coverage at the target precision
(cov@98) after the veto pass. The retired 3-tier-cascade harness
(runner/gold/metrics/report) was removed; `head_eval` is the only eval.

Entry point: `prices.enrich.eval.head_eval.run()` (also `python run.py prices eval`).
"""

from prices.enrich.eval.head_eval import run

__all__ = ["run"]
