"""Are the matched gold rows only the ones production already accepts?"""
import pandas as pd, numpy as np
from pathlib import Path

B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
TAU = 0.9436536386510268

g = pd.read_parquet("/tmp/gold_matched_uv.parquet")
oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["gold_row_id", "calibrated_correctness_score_oof",
                               "action_correct", "final_action", "proposed_leaf", "gold"])
m = g.merge(oof, on="gold_row_id", how="inner")
print(f"gold rows with a production unit value AND an OOF score: {len(m):,}")

s = m.calibrated_correctness_score_oof
print(f"\nOOF score distribution of the MATCHED rows:")
for q in (0.01, 0.05, 0.25, 0.5, 0.75):
    print(f"   p{int(q*100):<3} {s.quantile(q):.4f}")
above = (s >= TAU).sum()
print(f"\n  at or above production tau: {above:,} ({above/len(m):.1%})")
print(f"  BELOW production tau:       {len(m)-above:,} ({1-above/len(m):.1%})")
print(f"  wrong (action_correct==False): {(~m.action_correct).sum():,}")
below_wrong = ((s < TAU) & ~m.action_correct).sum()
print(f"  below tau AND wrong: {below_wrong:,}  <- the population the test needs")

if below_wrong < 500:
    print("\n>>> TOO FEW. The build is accept-only; must use decisions_hierlex.")
else:
    print("\n>>> Usable directly.")

# How is input_hash built? Needed if we fall back to the decisions cache.
import subprocess
print("\n=== input_hash provenance ===")
print(subprocess.run(
    ["grep", "-rn", "input_hash", "src/prices/enrich/stages/classify.py"],
    capture_output=True, text=True).stdout[:1200])
