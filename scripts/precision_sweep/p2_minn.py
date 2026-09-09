"""Is the median-movement tail concentrated in thin cells?

If it is, the control for relaxation is a minimum-n publication rule -- which
is a property of the cell, knowable in advance, and needs no ability to tell a
wrong row from a right one. That is the opposite of a dispersion gate, and the
Phase 0 result says a dispersion gate is the one thing we cannot have.
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

rng = np.random.default_rng(20260909)
OBS = "data/prices/build/global_prices_observations.parquet"

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

pub = obs[(obs.qa_status == "trusted") & obs.unit_value_usd.notna()
          & (obs.unit_value_usd > 0)]
cut = pd.Timestamp.now().normalize() - pd.Timedelta(days=60)
pub = pub[pub.observation_date >= cut]
pub = pub.assign(cell=pub.coicop_code.astype(str) + "|" + pub.country.astype(str)
                 + "|" + pub.standard_unit.astype(str))
vals = {k: v.to_numpy() for k, v in pub.groupby("cell", observed=True).unit_value_usd}
vals = {k: v for k, v in vals.items() if len(v) >= 3}

P = 0.05                      # the 95% target: contamination = 1 - precision
sizes = np.array([len(v) for v in vals.values()])
mv = np.empty(len(vals))
for i, v in enumerate(vals.values()):
    nb = int(rng.binomial(len(v), P / (1 - P)))
    if nb == 0:
        mv[i] = 0.0
        continue
    bad = rng.choice(v, size=nb, replace=True) * np.exp(rng.choice(OFF, size=nb, replace=True))
    mv[i] = abs(np.median(np.concatenate([v, bad])) - np.median(v)) / np.median(v)

BUCKETS = [(3, 5), (5, 10), (10, 30), (30, 100), (100, 1000), (1000, 10**9)]
hdr = "%-12s %8s %9s %8s %8s %8s" % ("cell n", "cells", "med move", "p90", ">5%", ">10%")
print("MEDIAN MOVEMENT AT THE 95%% TARGET, BY CELL SIZE")
print(hdr)
print("-" * len(hdr))
for lo, hi in BUCKETS:
    s = (sizes >= lo) & (sizes < hi)
    if not s.any():
        continue
    d = mv[s]
    print("%-12s %8s %8.2f%% %7.2f%% %7.1f%% %7.1f%%" % (
        "%d-%d" % (lo, hi - 1) if hi < 10**9 else "%d+" % lo,
        format(int(s.sum()), ","), np.median(d) * 100,
        np.quantile(d, .9) * 100, (d > .05).mean() * 100, (d > .10).mean() * 100))

print("\nWHAT A MINIMUM-n PUBLICATION RULE BUYS")
print("%-10s %9s %9s %9s %10s" % ("min n", "cells kept", "share", ">5% move", "rows kept"))
tot_rows = sizes.sum()
for k in (3, 5, 10, 20, 30, 50):
    s = sizes >= k
    d = mv[s]
    print("%-10s %9s %8.1f%% %8.1f%% %9.1f%%" % (
        k, format(int(s.sum()), ","), s.mean() * 100,
        (d > .05).mean() * 100, sizes[s].sum() / tot_rows * 100))
