"""If the gate cannot remove the contamination, how much does it actually hurt?

The dashboard publishes a per-cell MEDIAN. A median is robust to contamination
that is price-compatible -- which is exactly what the AUC 0.4995 result says
this contamination is. Simulate it: inject wrong rows drawn the way real
misclassification draws them (other leaves, same country and unit), at the
marginal error rates measured from OOF, and measure how far the published
median moves.
"""
import pandas as pd, pyarrow.parquet as pq, numpy as np

rng = np.random.default_rng(20260909)
OBS = "data/prices/build/global_prices_observations.parquet"

f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_usd", "qa_status",
        "observation_date"]
parts = []
for i in range(f.metadata.num_row_groups):
    d = f.read_row_group(i, columns=cols).to_pandas()
    d = d[(d.qa_status == "trusted") & d.unit_value_usd.notna() & (d.unit_value_usd > 0)]
    parts.append(d.drop(columns=["qa_status"]))
df = pd.concat(parts, ignore_index=True)
del parts
cut = pd.Timestamp.now().normalize() - pd.Timedelta(days=60)
df = df[df.observation_date >= cut].drop(columns=["observation_date"])
print(f"published-window trusted rows: {len(df):,}")

df["cell"] = (df.coicop_code.astype(str) + "|" + df.country.astype(str)
              + "|" + df.standard_unit.astype(str))
df["pool"] = df.country.astype(str) + "|" + df.standard_unit.astype(str)
base = df.groupby("cell").unit_value_usd.agg(["median", "size"])
base = base[base["size"] >= 3]
print(f"cells with n>=3: {len(base):,}")

pools = {k: v.to_numpy() for k, v in df.groupby("pool").unit_value_usd}
cell_pool = df.groupby("cell").pool.first()
cell_vals = {k: v.to_numpy() for k, v in df.groupby("cell").unit_value_usd}

# Marginal error rates measured from OOF earlier.
SCEN = [("98% target", 0.142), ("95% target", 0.264),
        ("92% target", 0.365), ("90% target", 0.426)]

print(f"\n{'scenario':<14}{'contam':>8}{'cells':>8}{'med |move|':>12}"
      f"{'>5%':>8}{'>10%':>8}{'>25%':>8}{'>50%':>8}")
for lab, p in SCEN:
    moves = []
    for cell, m0 in base["median"].items():
        v = cell_vals[cell]
        n_bad = int(round(len(v) * p / (1 - p)))
        if n_bad == 0:
            moves.append(0.0)
            continue
        pool = pools[cell_pool[cell]]
        bad = rng.choice(pool, size=min(n_bad, len(pool)), replace=len(pool) < n_bad)
        m1 = np.median(np.concatenate([v, bad]))
        moves.append(abs(m1 - m0) / m0)
    mv = np.array(moves)
    print(f"{lab:<14}{p:>7.1%}{len(mv):>8,}{np.median(mv):>11.2%}"
          f"{(mv>.05).mean():>8.1%}{(mv>.10).mean():>8.1%}"
          f"{(mv>.25).mean():>8.1%}{(mv>.50).mean():>8.1%}")

print("\nNOTE: this is a WORST CASE. Contamination is drawn from the whole")
print("country x unit pool, i.e. every wrong row comes from a different leaf.")
print("Real confusion is concentrated among NEIGHBOURING leaves, whose prices")
print("are closer, so true median movement is smaller than shown.")
