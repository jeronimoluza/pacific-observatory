"""GO/NO-GO: does the dispersion gate catch real misclassifications?

Natural experiment. 10,281 gold rows sit in production having been accepted on
an IN-SAMPLE score, while their out-of-fold score puts them below tau. They are
therefore a sample of exactly what relaxation admits -- already carrying unit
values and audit verdicts computed by the real pipeline. 2,257 of them are known
wrong. So: what fraction did the audit flag?
"""
import pandas as pd, pyarrow.parquet as pq, numpy as np
from pathlib import Path

OBS = "data/prices/build/global_prices_observations.parquet"
B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
TAU = 0.9436536386510268

gold = pd.read_parquet("data/prices/enrich/gold/gold_labels.parquet",
                       columns=["gold_row_id", "product_name", "country", "code", "verdict"])
gold = gold[gold.verdict == "leaf"].drop(columns="verdict")
gold["k"] = gold.country.astype(str) + "\x00" + gold.product_name.astype(str)
want = set(gold.k)

f = pq.ParquetFile(OBS)
cols = ["country", "product_name", "coicop_code", "standard_unit", "unit_value_local",
        "uv_robust_z", "uv_cell_n", "uv_outlier", "uv_thin", "trust_uv",
        "qa_status", "mass_source", "unit_value_usd"]
hits = []
for i in range(f.metadata.num_row_groups):
    d = f.read_row_group(i, columns=cols).to_pandas()
    d["k"] = d.country.astype(str) + "\x00" + d.product_name.astype(str)
    d = d[d.k.isin(want)]
    if len(d):
        hits.append(d.drop(columns=["product_name", "country"]))
obs = pd.concat(hits, ignore_index=True)
print(f"matched production rows: {len(obs):,}")

agg = obs.groupby("k").agg(
    uv=("unit_value_local", "median"),
    uv_usd=("unit_value_usd", "median"),
    absz=("uv_robust_z", lambda s: s.abs().max()),
    cell_n=("uv_cell_n", "max"),
    outlier=("uv_outlier", "max"),
    thin=("uv_thin", "max"),
    flagged=("trust_uv", lambda s: (s == "flag").any()),
    trusted=("qa_status", lambda s: (s == "trusted").any()),
    assigned=("coicop_code", lambda s: s.mode().iat[0] if len(s.mode()) else None),
    unit=("standard_unit", lambda s: s.mode().iat[0] if len(s.mode()) else None),
)

oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["gold_row_id", "calibrated_correctness_score_oof",
                               "action_correct", "gold"])
m = gold.set_index("k").join(agg, how="inner").reset_index().merge(
    oof, on="gold_row_id", how="inner")
m["below"] = m.calibrated_correctness_score_oof < TAU
m["wrong"] = ~m.action_correct
print(f"joined: {len(m):,}   below tau: {m.below.sum():,}   wrong: {m.wrong.sum():,}")

sub = m[m.below]
w, r = sub[sub.wrong], sub[~sub.wrong]
print(f"\n=== the population relaxation admits ({len(sub):,} rows) ===")
print(f"  known WRONG:   {len(w):,}")
print(f"  known CORRECT: {len(r):,}")

print(f"\n=== GATE RECALL against real misclassification ===")
print(f"{'verdict':<28}{'WRONG rows':>14}{'CORRECT rows':>15}{'  (false alarm)':>16}")
for lab, cw, cr in (
    ("uv_outlier fired", w.outlier.fillna(False).mean(), r.outlier.fillna(False).mean()),
    ("trust_uv == flag", w.flagged.fillna(False).mean(), r.flagged.fillna(False).mean()),
    ("uv_thin (unjudgeable)", w.thin.fillna(False).mean(), r.thin.fillna(False).mean()),
    ("reached qa_status trusted", w.trusted.fillna(False).mean(), r.trusted.fillna(False).mean()),
):
    print(f"{lab:<28}{cw:>13.1%}{cr:>15.1%}")

print(f"\n=== recall if we TIGHTEN k (|robust z| threshold) ===")
print(f"{'k':>5}{'catches WRONG':>16}{'cuts CORRECT':>15}{'ratio':>9}")
for k in (5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0):
    cw = (w.absz.abs() > k).mean()
    cr = (r.absz.abs() > k).mean()
    print(f"{k:>5.1f}{cw:>15.1%}{cr:>15.1%}{(cw/cr if cr else np.inf):>9.2f}x")

print(f"\nrows with NO z at all (unjudgeable): wrong {w.absz.isna().mean():.1%}, "
      f"correct {r.absz.isna().mean():.1%}")

print("\n=== are the wrong rows even in a different PRICE REGIME? ===")
print("log10 unit_value_usd, wrong vs correct, among below-tau rows:")
for lab, d in (("wrong", w), ("correct", r)):
    v = np.log10(d.uv_usd.replace(0, np.nan).dropna())
    print(f"  {lab:<8} n={len(v):>6,}  p10 {v.quantile(.1):>6.2f}  med {v.median():>6.2f}"
          f"  p90 {v.quantile(.9):>6.2f}")
m.to_parquet("/tmp/p0_joined.parquet", index=False)
print("\nwrote /tmp/p0_joined.parquet")
