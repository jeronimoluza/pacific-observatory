"""Does weighting rows by confidence protect the published median?

Phase 1 said yes, but measured it under the contamination model p0_median.py
got wrong, so the magnitude cannot be trusted. This repeats it under the
corrected model: contamination at 1 - precision, offsets drawn from real wrong
rows, and confidence scores drawn from the real joint distribution of score and
correctness at each operating point -- so a bad row carries the low score a bad
row actually carries, rather than an assumed one.
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

rng = np.random.default_rng(20260909)
B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
OBS = "data/prices/build/global_prices_observations.parquet"

# ---- offsets of real wrong rows (as in p2_move) -------------------------------
m = pd.read_parquet("/tmp/p0_joined.parquet")
sub = m[m.below].copy()
f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_local",
        "unit_value_usd", "qa_status", "observation_date"]
obs = pd.concat([f.read_row_group(i, columns=cols).to_pandas()
                 for i in range(f.metadata.num_row_groups)], ignore_index=True)
loc = obs[obs.unit_value_local.notna() & (obs.unit_value_local > 0)]
cl = (loc.groupby(["coicop_code", "country", "standard_unit"], observed=True)
        .unit_value_local.agg(cmed="median", cn="size").reset_index())
cl = cl[cl.cn >= 3]
for c in ("coicop_code", "country", "standard_unit"):
    cl[c] = cl[c].astype(str)
for c in ("assigned", "country", "unit"):
    sub[c] = sub[c].astype(str)
j = sub.merge(cl.rename(columns={"coicop_code": "assigned", "standard_unit": "unit"}),
              on=["assigned", "country", "unit"], how="left")
j["lr"] = np.log(j.uv / j.cmed)
OFF = j.loc[j.wrong & j.lr.notna() & np.isfinite(j.lr), "lr"].to_numpy()

# ---- real score distributions of correct and wrong rows, per operating point --
oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["calibrated_correctness_score_oof", "action_correct"])
S, A = oof.calibrated_correctness_score_oof.to_numpy(), oof.action_correct.to_numpy()

pub = obs[(obs.qa_status == "trusted") & obs.unit_value_usd.notna()
          & (obs.unit_value_usd > 0)]
cut = pd.Timestamp.now().normalize() - pd.Timedelta(days=60)
pub = pub[pub.observation_date >= cut]
pub = pub.assign(cell=pub.coicop_code.astype(str) + "|" + pub.country.astype(str)
                 + "|" + pub.standard_unit.astype(str))
vals = [v.to_numpy() for _, v in pub.groupby("cell", observed=True).unit_value_usd]
vals = [v for v in vals if len(v) >= 3]
print("published cells with n>=3: %s" % format(len(vals), ","))


def wmedian(x, w):
    o = np.argsort(x)
    x, w = x[o], w[o]
    c = np.cumsum(w)
    return x[np.searchsorted(c, c[-1] / 2.0)]


SCEN = [("98pct", 0.9376, 0.020), ("95pct", 0.5893, 0.050),
        ("92pct", 0.1713, 0.080), ("90pct", 0.0730, 0.100)]
hdr = "%-8s %8s %10s %9s %10s %9s %8s" % (
    "target", "contam", "plain >5%", "wtd >5%", "plain p99", "wtd p99", "cut")
print("\nPLAIN vs CONFIDENCE-WEIGHTED CELL MEDIAN")
print(hdr)
print("-" * len(hdr))
for lab, t, p in SCEN:
    sel = S >= t
    sc_ok, sc_bad = S[sel & A], S[sel & ~A]
    if len(sc_bad) < 50:
        sc_bad = S[~A]
    pm = np.empty(len(vals))
    wm = np.empty(len(vals))
    for i, v in enumerate(vals):
        nb = int(rng.binomial(len(v), p / (1 - p)))
        m0 = np.median(v)
        wg = rng.choice(sc_ok, size=len(v), replace=True)
        if nb == 0:
            pm[i] = 0.0
            wm[i] = abs(wmedian(v, wg) - m0) / m0
            continue
        bad = rng.choice(v, size=nb, replace=True) * np.exp(
            rng.choice(OFF, size=nb, replace=True))
        wb = rng.choice(sc_bad, size=nb, replace=True)
        allv = np.concatenate([v, bad])
        pm[i] = abs(np.median(allv) - m0) / m0
        wm[i] = abs(wmedian(allv, np.concatenate([wg, wb])) - m0) / m0
    red = (1 - (wm > .05).mean() / max((pm > .05).mean(), 1e-9)) * 100
    print("%-8s %7.1f%% %9.1f%% %8.1f%% %9.1f%% %8.1f%% %7.0f%%" % (
        lab, p * 100, (pm > .05).mean() * 100, (wm > .05).mean() * 100,
        np.quantile(pm, .99) * 100, np.quantile(wm, .99) * 100, red))
print("\n'cut' = reduction in the share of cells moving more than 5%.")
print("Weighting keeps every row; it only changes how much each one counts.")
