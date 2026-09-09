"""Do the gold rows carrying a production unit value reach the deep score bands?

The Phase 0 bias check established that the matched set skews toward rows
production already accepts. Before any per-band claim is made, measure how far
down the score range that matched set actually reaches, against the full OOF
population as the denominator.
"""
import pandas as pd
from pathlib import Path

B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")

g = pd.read_parquet("/tmp/gold_matched_uv.parquet")
oof = pd.read_parquet(
    B / "audit/implementation_oof_decisions.parquet",
    columns=["gold_row_id", "calibrated_correctness_score_oof", "action_correct",
             "proposed_leaf", "gold", "country", "outer_fold"])
m = g.merge(oof, on="gold_row_id", how="inner")
print(f"matched rows: {len(m):,}   of {len(oof):,} OOF rows")

# Band edges are the taus each precision target implies, from the p0 curve.
EDGES = [("at/above prod tau", 0.9437, 1.01),
         ("98pct  .9376-.9437", 0.9376, 0.9437),
         ("95pct  .5893-.9376", 0.5893, 0.9376),
         ("92pct  .1713-.5893", 0.1713, 0.5893),
         ("90pct  .0730-.1713", 0.0730, 0.1713),
         ("below  .0730",      -0.01,  0.0730)]

s = m["calibrated_correctness_score_oof"]
a = oof["calibrated_correctness_score_oof"]

hdr = "%-20s %9s %8s %8s   | %9s %8s %8s" % (
    "band", "matched", "wrong", "prec", "all OOF", "wrong", "prec")
print("\n" + hdr)
print("-" * len(hdr))
for lab, lo, hi in EDGES:
    sub = m[(s >= lo) & (s < hi)]
    asub = oof[(a >= lo) & (a < hi)]
    pm = sub["action_correct"].mean() if len(sub) else float("nan")
    pa = asub["action_correct"].mean() if len(asub) else float("nan")
    print("%-20s %9s %8s %7.1f%%   | %9s %8s %7.1f%%" % (
        lab, format(len(sub), ","), format(int((~sub["action_correct"]).sum()), ","),
        pm * 100, format(len(asub), ","),
        format(int((~asub["action_correct"]).sum()), ","), pa * 100))

# The decisive number: what share of each band survives into the matched set?
print("\nmatch rate per band (how representative the unit-value sample is):")
for lab, lo, hi in EDGES:
    n_all = int(((a >= lo) & (a < hi)).sum())
    n_m = int(((s >= lo) & (s < hi)).sum())
    rate = n_m / n_all if n_all else float("nan")
    verdict = "usable" if n_m >= 500 else "TOO THIN"
    print("  %-20s %6.1f%%   n=%-8s %s" % (lab, rate * 100, format(n_m, ","), verdict))
