"""Pin down the tau to ship, and measure how honest its precision target is.

Two things make the headline "95% target -> tau 0.5893" optimistic, and both
have to be quantified before the number is baked into config:

  1. p0_curve solved with `ok[-1]`, the LAST index whose running precision
     clears the target. Running precision is not monotone, so the last crossing
     sits deeper than the first and claims coverage the curve does not hold
     everywhere above it.
  2. tau was chosen on the same rows its precision was measured on. The target
     is therefore in-sample even though the SCORES are out-of-fold.

Cross-validating on `outer_fold` -- choose tau on four folds, measure on the
fifth -- separates the two.
"""
import numpy as np
import pandas as pd
from pathlib import Path

B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["calibrated_correctness_score_oof", "action_correct",
                               "outer_fold", "gold"])
s = oof["calibrated_correctness_score_oof"].to_numpy(float)
c = oof["action_correct"].to_numpy(bool)
fold = oof["outer_fold"].to_numpy()
n = len(s)
TAU_PROD = 0.9436536386510268


def solve(sv, cv, target, last=True):
    """Smallest tau whose accepted set still meets `target` precision."""
    o = np.argsort(-sv)
    cum = np.cumsum(cv[o].astype(float)) / (np.arange(len(sv)) + 1)
    ok = np.where(cum >= target)[0]
    if not len(ok):
        return None
    if last:
        i = ok[-1]
    else:                      # first break: the contiguous prefix that holds
        brk = np.where(np.diff(ok) > 1)[0]
        i = ok[brk[0]] if len(brk) else ok[-1]
    return float(sv[o][i])


def report(sv, cv, tau):
    a = sv >= tau
    return (float(cv[a].mean()) if a.any() else float("nan"),
            float((cv & a).sum() / len(sv)), int(a.sum()))


print("TAU BY SOLVER DEFINITION (all 278,490 OOF rows)")
hdr = "%-8s %12s %12s %10s %10s %11s" % (
    "target", "tau (last)", "tau (first)", "prec last", "prec 1st", "cov last")
print(hdr)
print("-" * len(hdr))
TAUS = {}
for t in (0.98, 0.95, 0.92, 0.90):
    tl = solve(s, c, t, last=True)
    tf = solve(s, c, t, last=False)
    pl, cl, _ = report(s, c, tl)
    pf, _, _ = report(s, c, tf)
    TAUS[t] = (tl, tf)
    print("%-8s %12.6f %12.6f %9.3f%% %9.3f%% %10.3f%%"
          % ("%.0f%%" % (t * 100), tl, tf, pl * 100, pf * 100, cl * 100))

print("\nCROSS-VALIDATED: tau chosen on 4 folds, precision measured on the 5th")
hdr = "%-8s %11s %13s %13s %10s" % (
    "target", "mean tau", "in-sample prec", "held-out prec", "gap")
print(hdr)
print("-" * len(hdr))
for t in (0.98, 0.95, 0.92, 0.90):
    taus, precs, covs = [], [], []
    for f in np.unique(fold):
        tr, te = fold != f, fold == f
        tau = solve(s[tr], c[tr], t, last=True)
        if tau is None:
            continue
        p, cov, _ = report(s[te], c[te], tau)
        taus.append(tau)
        precs.append(p)
        covs.append(cov)
    ins = report(s, c, TAUS[t][0])[0]
    print("%-8s %11.6f %12.3f%% %12.3f%% %+9.3f"
          % ("%.0f%%" % (t * 100), np.mean(taus), ins * 100,
             np.mean(precs) * 100, (np.mean(precs) - ins) * 100))
    print("         per-fold tau spread: %s"
          % "  ".join("%.4f" % x for x in taus))

print("\nSTABILITY: how much coverage moves for a small tau error, 95%% target")
tl = TAUS[0.95][0]
for d in (-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10):
    p, cov, acc = report(s, c, min(max(tl + d, 0.0), 1.0))
    print("  tau %+.2f = %.4f -> precision %6.3f%%  coverage %6.3f%%  accepted %s"
          % (d, tl + d, p * 100, cov * 100, format(acc, ",")))

fb = oof["gold"].astype(str).str.startswith(("01.", "02.")).to_numpy()
print("\nFOOD & BEVERAGE at the shipped taus (%s rows)" % format(int(fb.sum()), ","))
pb, cb, _ = report(s[fb], c[fb], TAU_PROD)
print("  production  : precision %.3f%%  coverage %.3f%%" % (pb * 100, cb * 100))
for t in (0.98, 0.95):
    p, cov, _ = report(s[fb], c[fb], TAUS[t][0])
    print("  %.0f%% target : precision %.3f%%  coverage %.3f%%  (%+.3f pts)"
          % (t * 100, p * 100, cov * 100, (cov - cb) * 100))
