"""The decisive number: how dirty is the MARGINAL row?

Overall precision at a relaxed target flatters the trade, because the rows
already accepted at production tau keep holding it up. What the dispersion gate
has to survive is the error rate of the rows relaxation ADDS.
"""

import numpy as np
import pandas as pd
from pathlib import Path

B = Path.home() / "po/data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908"
oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet")
s = oof["calibrated_correctness_score_oof"].to_numpy(float)
c = oof["action_correct"].to_numpy(bool)
n = len(s)
TAU_PROD = 0.9436536386510268

order = np.argsort(-s)
cs, cc = s[order], c[order]
cum = np.cumsum(cc.astype(float)) / (np.arange(n) + 1)


def tau_for(target):
    ok = np.where(cum >= target)[0]
    return float(cs[ok[-1]]) if len(ok) else None


base = s >= TAU_PROD
print(f"production accepts {base.sum():,}  ({(~c[base]).sum():,} of them wrong)\n")
print("=== precision of the rows each target NEWLY admits ===")
print(f"{'target':>7}{'tau':>10}{'new rows':>10}{'new correct':>12}{'new WRONG':>11}"
      f"{'marginal prec':>15}{'wrong rows total':>18}{'x prod':>8}")
rows = []
for t in (0.98, 0.97, 0.96, 0.95, 0.92, 0.90):
    tau = tau_for(t)
    a = s >= tau
    new = a & ~base
    nw = int((~c[new]).sum())
    mp = float(c[new].mean()) if new.any() else float("nan")
    tot_w = int((~c[a]).sum())
    rows.append((t, tau, int(new.sum()), int(c[new].sum()), nw, mp, tot_w))
    print(f"{t:>7.0%}{tau:>10.4f}{new.sum():>10,}{int(c[new].sum()):>12,}{nw:>11,}"
          f"{mp:>14.1%}{tot_w:>18,}{tot_w/(~c[base]).sum():>8.1f}x")

print("\nRead: at a 95% target, ~1 in 4 added rows is misclassified.")
print("The MAD breakdown point is 50% contamination -- but it degrades long")
print("before that, and 'bad rows become their own norm' is the documented")
print("production failure (Slovak 100x). This is why the baseline mask matters.")

# How concentrated is the damage? If wrong rows pile into a few leaves, a
# support gate fixes it cheaply. If they spread, it does not.
print("\n=== do the newly-wrong rows concentrate in a few leaves? ===")
for t in (0.95, 0.92):
    tau = tau_for(t)
    new = (s >= tau) & ~base
    w = oof.loc[new & ~c, "gold"].astype(str)
    vc = w.value_counts()
    tot = len(w)
    print(f"\ntarget {t:.0%}: {tot:,} newly-wrong rows across {vc.nunique() and len(vc)} gold leaves")
    print(f"  top 10 leaves hold {vc.head(10).sum()/tot:.1%};"
          f" top 50 hold {vc.head(50).sum()/tot:.1%}")
    fb = w.str.startswith(("01.", "02."))
    print(f"  food & beverage share of the new errors: {fb.mean():.1%}")
    for code, k in vc.head(6).items():
        print(f"    {code:<12} {k:>6,}  ({k/tot:4.1%})")
