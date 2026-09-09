# Precision-target sweep — Phase 0

Does lowering the classifier's precision target (98% → 95/92/90) pay, and can a
per-cell log-MAD gate on unit values police the result?

Run from this worktree; `data/` is symlinked to the production tree.

    PYTHONPATH=src ~/venv/bin/python scripts/precision_sweep/p0_curve.py

| script | question |
|---|---|
| `p0_curve.py` | control + coverage/precision curve. Targets vs tau values. |
| `p0_marginal.py` | precision of the rows each target NEWLY admits |
| `p0_match.py` | match gold rows to production observations by (country, name) |
| `p0_bias.py` | is the matched set only rows production already accepts? |
| `p0_recall.py` | **go/no-go**: gate recall against real misclassification |
| `p0_verify.py` | AUC + positive control + density strata |
| `p0_median.py` | how far a published cell median moves under contamination |

## Verdict

The dispersion gate **cannot** police relaxation: AUC 0.4995 against
misclassification, versus 0.7835 for the same statistic against implausible
absolute unit values. Tightening k makes it worse. Misclassified products are
price-compatible with the cells they land in (Cohen's d −0.089).

But the same fact makes the published **median** robust: worst-case movement is
3.37% at the 95% target. The case for relaxation is median robustness plus the
fact that a missing cell is worse than a slightly biased one — not downstream
filtering.

Control: `p0_curve.py` reproduces the shipped operating point exactly
(219,713 accepted, precision 98.1644%, coverage 77.4462%).
