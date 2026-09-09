"""Accuracy at every level of the COICOP hierarchy, not just the leaf.

William's point: being off at the leaf while right at the class is a different
kind of wrong from landing in another division. A single leaf-exact number
cannot tell those apart, and it is the number that makes relaxation look
expensive.

Mirrors what the pipeline actually publishes: `backends._score_hierlex` keeps
the PROPOSED leaf wherever the bundle's parent-fallback rewrote one onto a real
n.e.c. sibling, so the revised leaf is scored here, with the raw `final_action`
alongside to show what the rewrite costs.
"""
import numpy as np
import pandas as pd
from pathlib import Path

from prices.enrich.hierlex import scorer

B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["calibrated_correctness_score_oof", "action_correct",
                               "final_action", "proposed_leaf", "is_fallback",
                               "gold"])
n = len(oof)
s = oof["calibrated_correctness_score_oof"].to_numpy(float)

gold = oof["gold"].astype(str)
raw = oof["final_action"].astype(str)
# `is_leaf` is not in the audit; the synthetic token is the only non-leaf form.
is_leaf = ~raw.str.contains("__parent_fallback__", regex=False)
revised = raw.where(~(oof["is_fallback"].astype(bool) & is_leaf),
                    oof["proposed_leaf"].astype(str))


def depth_match(pred, truth, d):
    """Do the first `d` dot-separated components agree?"""
    p = pred.str.split(".").str[:d].str.join(".")
    t = truth.str.split(".").str[:d].str.join(".")
    return (p == t).to_numpy()


LEVELS = [(1, "division"), (2, "group"), (3, "class"),
          (4, "subclass"), (5, "leaf")]
MATCH = {d: depth_match(revised, gold, d) for d, _ in LEVELS}
MATCH_RAW = {d: depth_match(raw, gold, d) for d, _ in LEVELS}

POINTS = [("conservative_risk (was)", scorer.resolve_tau(policy="conservative_risk")),
          ("empirical_98", scorer.resolve_tau(policy="empirical_98")),
          ("target_95 (now)", scorer.resolve_tau(policy="target_95")),
          ("target_92", scorer.resolve_tau(policy="target_92")),
          ("target_90", scorer.resolve_tau(policy="target_90"))]

# "accept" is the ACCEPTANCE RATE (accepted / all), not the coverage figure
# quoted elsewhere in this sweep, which is (accepted AND correct) / all. The two
# differ by several points at every operating point and confusing them overstates
# what relaxation buys.
hdr = "%-24s %9s %8s | %8s %8s %8s %9s %8s" % (
    "operating point", "accepted", "accept", "division", "group", "class",
    "subclass", "LEAF")
print("ACCURACY BY COICOP DEPTH, among ACCEPTED rows (278,490 OOF gold rows)")
print(hdr)
print("-" * len(hdr))
for lab, tau in POINTS:
    a = s >= tau
    row = "%-24s %9s %7.1f%% |" % (lab, format(int(a.sum()), ","), a.sum() / n * 100)
    for d, _ in LEVELS:
        row += " %7.2f%%" % (MATCH[d][a].mean() * 100)
    print(row)

print("\nSAME, restricted to food and beverage (divisions 01 and 02)")
fb = gold.str.startswith(("01.", "02.")).to_numpy()
print(hdr)
print("-" * len(hdr))
for lab, tau in POINTS:
    a = (s >= tau) & fb
    row = "%-24s %9s %7.1f%% |" % (lab, format(int(a.sum()), ","),
                                   a.sum() / fb.sum() * 100)
    for d, _ in LEVELS:
        row += " %7.2f%%" % (MATCH[d][a].mean() * 100)
    print(row)

print("\nWHERE THE LEAF ERRORS LAND, at the 95%% target")
a = s >= scorer.resolve_tau(policy="target_95")
wrong = a & ~MATCH[5]
print("  accepted %s, leaf-wrong %s (%.2f%%)"
      % (format(int(a.sum()), ","), format(int(wrong.sum()), ","),
         wrong.sum() / a.sum() * 100))
tot = int(wrong.sum())
prev = 0
for d, name in LEVELS[:4]:
    # Of the leaf-wrong rows, how many are still right this far up?
    k = int((wrong & MATCH[d]).sum())
    print("    still correct at %-9s %8s  (%5.1f%% of leaf errors)"
          % (name, format(k, ","), k / tot * 100))
deepest = wrong & ~MATCH[1]
print("    wrong even at division  %8s  (%5.1f%% of leaf errors)"
      % (format(int(deepest.sum()), ","), deepest.sum() / tot * 100))

print("\nCOST OF THE PARENT-FALLBACK REVISION (accepted at the 95%% target)")
for d, name in LEVELS:
    print("  %-9s revised %6.2f%%   raw final_action %6.2f%%"
          % (name, MATCH[d][a].mean() * 100, MATCH_RAW[d][a].mean() * 100))
