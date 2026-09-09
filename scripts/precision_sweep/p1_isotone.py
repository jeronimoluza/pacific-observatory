"""The isotone idea: anchor the price on the confident tier, then require the
less-confident tiers to sit progressively closer to that anchor.

Tier A (>= production tau)  -> defines the anchor. Wide/no band.
Tier B (95% band)           -> admitted only within k_B robust MADs of A.
Tier C (90% band)           -> admitted only within k_C < k_B.

Compared against plain weighting on the SAME cells and the same draws.
Also: the structural question -- how often does an anchor even exist?
"""
import pandas as pd, pyarrow.parquet as pq, numpy as np
from pathlib import Path

rng = np.random.default_rng(20260909)
B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
OBS = "data/prices/build/global_prices_observations.parquet"

oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["calibrated_correctness_score_oof", "action_correct"])
s_all, c_all = (oof.calibrated_correctness_score_oof.to_numpy(float),
                oof.action_correct.to_numpy(bool))
n = len(s_all); o = np.argsort(-s_all)
cum = np.cumsum(c_all[o].astype(float)) / (np.arange(n) + 1)
tau_for = lambda t: float(s_all[o][np.where(cum >= t)[0][-1]])
TAU_P, TAU95, TAU90 = 0.9436536386510268, tau_for(0.95), tau_for(0.90)

# Per-tier score pools, split by correctness.
def pool(lo, hi):
    m = (s_all >= lo) & (s_all < hi)
    return s_all[m & c_all], s_all[m & ~c_all]
A_c, A_w = pool(TAU_P, 2.0)
Bc, Bw = pool(TAU95, TAU_P)
Cc, Cw = pool(TAU90, TAU95)
print(f"tier A (>= {TAU_P:.3f}): {len(A_c):,} correct / {len(A_w):,} wrong")
print(f"tier B ([{TAU95:.3f},{TAU_P:.3f})): {len(Bc):,} / {len(Bw):,}"
      f"   -> {len(Bw)/(len(Bc)+len(Bw)):.1%} wrong")
print(f"tier C ([{TAU90:.3f},{TAU95:.3f})): {len(Cc):,} / {len(Cw):,}"
      f"   -> {len(Cw)/(len(Cc)+len(Cw)):.1%} wrong")

f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_usd", "qa_status",
        "observation_date"]
parts = []
for i in range(f.metadata.num_row_groups):
    d = f.read_row_group(i, columns=cols).to_pandas()
    d = d[(d.qa_status == "trusted") & d.unit_value_usd.notna() & (d.unit_value_usd > 0)]
    parts.append(d.drop(columns=["qa_status"]))
df = pd.concat(parts, ignore_index=True); del parts
df = df[df.observation_date >= pd.Timestamp.now().normalize() - pd.Timedelta(days=60)]
df["cell"] = (df.coicop_code.astype(str)+"|"+df.country.astype(str)+"|"
              +df.standard_unit.astype(str))
df["pool"] = df.country.astype(str)+"|"+df.standard_unit.astype(str)
pools = {k: v.to_numpy() for k, v in df.groupby("pool").unit_value_usd}
cellv = {k: v.to_numpy() for k, v in df.groupby("cell").unit_value_usd}
cellp = df.groupby("cell").pool.first()
keys = [k for k, v in cellv.items() if len(v) >= 3]
print(f"\ncells n>=3: {len(keys):,}")


def wmed(v, w):
    i = np.argsort(v); v, w = v[i], w[i]
    cw = np.cumsum(w)
    return float(v[np.searchsorted(cw, cw[-1]/2.0)])


# Tier sizes relative to tier A, from the coverage deltas.
FRAC_B, FRAC_C = 0.111, 0.032   # B ~ +11.1% rows over A, C ~ +3.2% more
RES = {}
for kB, kC in ((np.inf, np.inf), (3.0, 2.0), (2.0, 1.0), (1.5, 0.75)):
    errs, kept = [], []
    for k in keys:
        vA = cellv[k]; truth = np.median(vA)
        pl = pools[cellp[k]]
        nB = max(1, int(len(vA)*FRAC_B)); nC = max(1, int(len(vA)*FRAC_C))
        wB = int(round(nB*len(Bw)/(len(Bc)+len(Bw))))
        wC = int(round(nC*len(Cw)/(len(Cc)+len(Cw))))
        vB = np.concatenate([rng.choice(vA, nB-wB, replace=True), rng.choice(pl, wB)])
        vC = np.concatenate([rng.choice(vA, nC-wC, replace=True), rng.choice(pl, wC)])
        lv = np.log(vA)
        anch = np.median(lv); mad = np.median(np.abs(lv-anch)) or 1e-9
        okB = np.abs(np.log(vB)-anch) <= kB*1.4826*mad
        okC = np.abs(np.log(vC)-anch) <= kC*1.4826*mad
        allv = np.concatenate([vA, vB[okB], vC[okC]])
        errs.append(abs(np.median(allv)-truth)/truth)
        kept.append((okB.sum()+okC.sum())/(len(vB)+len(vC)))
    e = np.array(errs); kp = np.array(kept)
    lab = "no band (accept all)" if kB == np.inf else f"k_B={kB}, k_C={kC}"
    RES[lab] = (np.median(e), (e > .05).mean(), kp.mean())
    print(f"{lab:<24} med|err| {np.median(e):>7.2%}   >5% {(e>.05).mean():>6.1%}"
          f"   kept {kp.mean():>6.1%} of relaxed rows")

# Weighting on the same construction, no band.
errs = []
for k in keys:
    vA = cellv[k]; truth = np.median(vA); pl = pools[cellp[k]]
    nB = max(1, int(len(vA)*FRAC_B)); nC = max(1, int(len(vA)*FRAC_C))
    wB = int(round(nB*len(Bw)/(len(Bc)+len(Bw)))); wC = int(round(nC*len(Cw)/(len(Cc)+len(Cw))))
    vB = np.concatenate([rng.choice(vA, nB-wB, True), rng.choice(pl, wB)])
    vC = np.concatenate([rng.choice(vA, nC-wC, True), rng.choice(pl, wC)])
    sA = rng.choice(np.concatenate([A_c, A_w]), len(vA))
    sB = rng.choice(np.concatenate([Bc, Bw]), len(vB))
    sC = rng.choice(np.concatenate([Cc, Cw]), len(vC))
    errs.append(abs(wmed(np.concatenate([vA,vB,vC]),
                         np.concatenate([sA,sB,sC]))-truth)/truth)
e = np.array(errs)
print(f"{'WEIGHTED (no band)':<24} med|err| {np.median(e):>7.2%}   >5% {(e>.05).mean():>6.1%}"
      f"   kept 100.0% of relaxed rows")
