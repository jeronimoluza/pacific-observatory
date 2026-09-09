"""CORRECTION + IDEA 1: weight rows by confidence instead of gating them.

Correction: cell contamination is (1 - precision), NOT the marginal error rate.
An earlier run used the marginal rate and overstated the damage ~5x.

Idea 1: the calibrated score IS P(correct). So a confidence-WEIGHTED median
estimates the price among correct rows without discarding anything. Test it
against hard thresholds, including accept-everything-and-weight.
"""
import pandas as pd, pyarrow.parquet as pq, numpy as np
from pathlib import Path

rng = np.random.default_rng(20260909)
B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
OBS = "data/prices/build/global_prices_observations.parquet"

oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["calibrated_correctness_score_oof", "action_correct"])
s_all = oof.calibrated_correctness_score_oof.to_numpy(float)
c_all = oof.action_correct.to_numpy(bool)
n = len(s_all)
o = np.argsort(-s_all)
cum = np.cumsum(c_all[o].astype(float)) / (np.arange(n) + 1)


def tau_for(t):
    ok = np.where(cum >= t)[0]
    return float(s_all[o][ok[-1]]) if len(ok) else -1.0


TAU_PROD = 0.9436536386510268
POL = [("production", TAU_PROD), ("98% target", tau_for(0.98)),
       ("95% target", tau_for(0.95)), ("92% target", tau_for(0.92)),
       ("90% target", tau_for(0.90)), ("accept ALL", -1.0)]
print(f"{'policy':<14}{'tau':>9}{'precision':>11}{'contamination':>15}{'coverage':>10}")
META = {}
for lab, t in POL:
    a = s_all >= t
    prec = c_all[a].mean()
    META[lab] = (t, 1 - prec, s_all[a & c_all], s_all[a & ~c_all])
    print(f"{lab:<14}{t:>9.4f}{prec:>10.3%}{1-prec:>15.2%}"
          f"{(c_all & a).sum()/n:>10.3%}")

# --- cells -------------------------------------------------------------------
f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_usd",
        "qa_status", "observation_date"]
parts = []
for i in range(f.metadata.num_row_groups):
    d = f.read_row_group(i, columns=cols).to_pandas()
    d = d[(d.qa_status == "trusted") & d.unit_value_usd.notna() & (d.unit_value_usd > 0)]
    parts.append(d.drop(columns=["qa_status"]))
df = pd.concat(parts, ignore_index=True); del parts
df = df[df.observation_date >= pd.Timestamp.now().normalize() - pd.Timedelta(days=60)]
df["cell"] = (df.coicop_code.astype(str) + "|" + df.country.astype(str) + "|"
              + df.standard_unit.astype(str))
df["pool"] = df.country.astype(str) + "|" + df.standard_unit.astype(str)
pools = {k: v.to_numpy() for k, v in df.groupby("pool").unit_value_usd}
cellv = {k: v.to_numpy() for k, v in df.groupby("cell").unit_value_usd}
cellp = df.groupby("cell").pool.first()
keys = [k for k, v in cellv.items() if len(v) >= 3]
print(f"\ncells with n>=3: {len(keys):,}")


def wmed(v, w):
    i = np.argsort(v)
    v, w = v[i], w[i]
    cw = np.cumsum(w)
    return float(v[np.searchsorted(cw, cw[-1] / 2.0)])


print(f"\n{'policy':<14}{'mode':<10}{'med |err|':>11}{'>5%':>8}{'>10%':>8}{'>25%':>8}")
for lab, _ in POL:
    tau, contam, sc, sw = META[lab]
    if contam <= 0 or len(sw) == 0:
        continue
    hard, soft = [], []
    for k in keys:
        v = cellv[k]
        truth = np.median(v)
        nb = int(round(len(v) * contam / (1 - contam)))
        if nb == 0:
            hard.append(0.0); soft.append(0.0); continue
        pool = pools[cellp[k]]
        bad = rng.choice(pool, size=nb, replace=nb > len(pool))
        allv = np.concatenate([v, bad])
        hard.append(abs(np.median(allv) - truth) / truth)
        w = np.concatenate([rng.choice(sc, len(v)), rng.choice(sw, nb)])
        soft.append(abs(wmed(allv, w) - truth) / truth)
    for mode, arr in (("hard", np.array(hard)), ("weighted", np.array(soft))):
        print(f"{lab:<14}{mode:<10}{np.median(arr):>10.2%}{(arr>.05).mean():>8.1%}"
              f"{(arr>.10).mean():>8.1%}{(arr>.25).mean():>8.1%}")
