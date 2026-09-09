"""How far does the PUBLISHED median move at each precision target?

Supersedes p0_median.py, which was wrong twice. It injected contamination at
the MARGINAL error rate (the share of newly-added rows that are wrong) where
the cell-level rate is 1 - precision, and it drew the bad rows from the whole
country x unit pool, which assumes every wrong row comes from an unrelated
leaf. Both inflate the damage.

The offsets used here are measured, not assumed: p2_recon established that a
wrong row sits 1.39x from its assigned cell's median against 1.46x for a
correct one, so contamination is drawn from the empirical offset distribution
of real wrong rows.
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

rng = np.random.default_rng(20260909)
OBS = "data/prices/build/global_prices_observations.parquet"

# ---- empirical offset of a real wrong row from its assigned cell median ------
m = pd.read_parquet("/tmp/p0_joined.parquet")
sub = m[m.below].copy()
f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_local",
        "unit_value_usd", "qa_status", "observation_date"]
parts = []
for i in range(f.metadata.num_row_groups):
    parts.append(f.read_row_group(i, columns=cols).to_pandas())
obs = pd.concat(parts, ignore_index=True)
del parts

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
print("empirical wrong-row offsets: n=%s  median |ratio| %.2fx  p90 %.2fx"
      % (format(len(OFF), ","), float(np.exp(np.median(np.abs(OFF)))),
         float(np.exp(np.quantile(np.abs(OFF), 0.9)))))

# ---- the published population ------------------------------------------------
pub = obs[(obs.qa_status == "trusted") & obs.unit_value_usd.notna()
          & (obs.unit_value_usd > 0)]
cut = pd.Timestamp.now().normalize() - pd.Timedelta(days=60)
pub = pub[pub.observation_date >= cut]
pub = pub.assign(cell=pub.coicop_code.astype(str) + "|" + pub.country.astype(str)
                 + "|" + pub.standard_unit.astype(str))
vals = {k: v.to_numpy() for k, v in pub.groupby("cell", observed=True).unit_value_usd}
vals = {k: v for k, v in vals.items() if len(v) >= 3}
print("published cells with n>=3: %s" % format(len(vals), ","))

# ---- contamination is 1 - precision at the operating point --------------------
SCEN = [("98pct target", 0.020), ("95pct target", 0.050),
        ("92pct target", 0.080), ("90pct target", 0.100)]
hdr = "%-14s %7s %10s %8s %8s %8s %8s" % (
    "target", "contam", "med move", "p90", "p99", ">5%", ">10%")
print("\nMOVEMENT OF THE PUBLISHED CELL MEDIAN")
print(hdr)
print("-" * len(hdr))
for lab, p in SCEN:
    mv = np.empty(len(vals))
    for i, v in enumerate(vals.values()):
        nb = int(rng.binomial(len(v), p / (1 - p)))
        if nb == 0:
            mv[i] = 0.0
            continue
        base = rng.choice(v, size=nb, replace=True)
        bad = base * np.exp(rng.choice(OFF, size=nb, replace=True))
        m1 = np.median(np.concatenate([v, bad]))
        m0 = np.median(v)
        mv[i] = abs(m1 - m0) / m0
    print("%-14s %6.1f%% %9.2f%% %7.2f%% %7.2f%% %7.1f%% %7.1f%%" % (
        lab, p * 100, np.median(mv) * 100, np.quantile(mv, .9) * 100,
        np.quantile(mv, .99) * 100, (mv > .05).mean() * 100,
        (mv > .10).mean() * 100))

# ---- the remaining risk: is contamination one-sided WITHIN a cell? ------------
print("\nONE-SIDEDNESS (pooled symmetry can hide per-cell bias)")
real = j[j.wrong & j.lr.notna() & np.isfinite(j.lr)]
g = real.groupby(["assigned", "country", "unit"]).lr.agg(["size", "mean"])
g = g[g["size"] >= 5]
print("  cells with >=5 real wrong rows: %s" % format(len(g), ","))
if len(g):
    print("  mean log offset per cell: median %+.3f, p10 %+.3f, p90 %+.3f"
          % (g["mean"].median(), g["mean"].quantile(.1), g["mean"].quantile(.9)))
    print("  cells biased >1.25x in one direction: %.1f%%"
          % ((g["mean"].abs() > np.log(1.25)).mean() * 100))
