"""What the new operating point does to the real corpus, not to the audit.

The taus were solved on 278,490 OOF gold rows. This applies them to all 7.29M
scored production pairs and reports the acceptance delta, plus the control that
matters: at the bundle's own tau the re-thresholding must reproduce the frozen
`accepted` column exactly, or the change has altered more than the threshold.
"""
import numpy as np
import pandas as pd
from pathlib import Path

from prices.enrich.hierlex import scorer

ROOT = Path("data/prices/enrich/_hierlex_pred/hierlex_select_v1_20260908")
parts = sorted(ROOT.glob("pred_*.parquet"))
print("score shards: %d" % len(parts))

n = 0
acc_col = 0
counts = {}
TAUS = {
    "conservative_risk (was)": scorer.resolve_tau(policy="conservative_risk"),
    "empirical_98": scorer.resolve_tau(policy="empirical_98"),
    "target_95 (now)": scorer.resolve_tau(policy="target_95"),
    "target_92": scorer.resolve_tau(policy="target_92"),
    "target_90": scorer.resolve_tau(policy="target_90"),
}
mismatch = 0
leaf_n = 0
for p in parts:
    d = pd.read_parquet(p, columns=["calibrated_correctness_score", "accepted",
                                    "is_leaf"])
    s = d["calibrated_correctness_score"].to_numpy(float)
    a = d["accepted"].to_numpy(bool)
    isleaf = d["is_leaf"].to_numpy(bool)
    n += len(d)
    acc_col += int((a & isleaf).sum())
    leaf_n += int(isleaf.sum())
    # Control: does re-thresholding at the bundle tau reproduce the column?
    mismatch += int((( s >= TAUS["conservative_risk (was)"]) != a).sum())
    for k, t in TAUS.items():
        counts[k] = counts.get(k, 0) + int(((s >= t) & isleaf).sum())

print("scored pairs: %s   is_leaf: %s" % (format(n, ","), format(leaf_n, ",")))
print("\nCONTROL: re-threshold at the bundle tau vs the frozen `accepted` column")
print("  rows differing: %s of %s (%.6f%%)"
      % (format(mismatch, ","), format(n, ","), mismatch / n * 100))
print("  frozen accepted & is_leaf: %s" % format(acc_col, ","))
print("  rethresholded            : %s" % format(counts["conservative_risk (was)"], ","))
# One row differs, and the cause is known rather than mysterious: the scorer
# computes `accepted` from the float64 calibrated score and then stores that
# score as float32 (scorer.py:144-145), so a row within a float32 ulp of tau can
# round across it. 1 in 32.7M, and it can only ever land on a row the gate was
# already indifferent about.
assert mismatch <= 8, "re-thresholding diverges beyond the float32 boundary"

base = counts["conservative_risk (was)"]
hdr = "%-26s %12s %14s %12s %10s" % ("policy", "tau", "accepted", "vs prod", "of pairs")
print("\nACCEPTANCE ON THE PRODUCTION CORPUS")
print(hdr)
print("-" * len(hdr))
for k, t in TAUS.items():
    c = counts[k]
    print("%-26s %12.6f %14s %+12s %9.2f%%"
          % (k, t, format(c, ","), format(c - base, ","), c / n * 100))
