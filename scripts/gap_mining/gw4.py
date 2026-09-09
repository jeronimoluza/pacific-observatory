"""How many world gap cells can sibling mining reach, and how deep is the pool?"""
import pathlib
import pandas as pd

O = pathlib.Path("outputs")
BANDS = ["b_lt90", "b_90", "b_92", "b_95", "b_98", "b_prod"]
REJ = ["b_lt90", "b_90", "b_92"]  # below the shipped tau 0.5893

G = pd.read_parquet(O / "world_triage_gaps.parquet")
C = pd.read_parquet(O / "parent_census.parquet")

P = C.pivot_table(index=["country", "parent_pred"], columns="band", values="n",
                  aggfunc="sum", fill_value=0, observed=True).reset_index()
for c in BANDS:
    if c not in P:
        P[c] = 0
P["fam"] = P[BANDS].sum(axis=1)
P["fam_rej"] = P[REJ].sum(axis=1)
P = P.rename(columns={"parent_pred": "parent"})[["country", "parent", "fam", "fam_rej"]]

G["parent"] = G.coicop.str.rsplit(".", n=1).str[0]
G = G.merge(P, on=["country", "parent"], how="left").fillna({"fam": 0, "fam_rej": 0})
G["fam"] = G.fam.astype(int)
G["fam_rej"] = G.fam_rej.astype(int)
G["reachable"] = G.fam_rej > 0

print("world gap cells: %d" % len(G))
print("sibling-reachable (parent family has rejected rows in-country): %d (%.1f%%)"
      % (G.reachable.sum(), 100 * G.reachable.mean()))
print("\nby bucket:")
print(G.groupby("bucket").agg(cells=("reachable", "size"), reachable=("reachable", "sum"),
                              pool=("fam_rej", "sum")).to_string())

# how concentrated is the reachable pool?
r = G[G.reachable]
print("\nreachable-cell family pool, quantiles:")
print(r.fam_rej.describe(percentiles=[.25, .5, .75, .9]).to_string())
print("\ncountries with >=1 reachable gap: %d of %d" % (r.country.nunique(), G.country.nunique()))
print("leaves with >=1 reachable gap: %d" % r.coicop.nunique())

G.to_parquet(O / "world_gaps_reach.parquet", index=False)
