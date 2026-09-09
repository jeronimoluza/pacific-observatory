"""World gap universe + triage at the shipped target_95 tau."""
import json, pathlib
import pandas as pd

O = pathlib.Path("outputs")
ACC = ["b_95", "b_98", "b_prod"]  # calibrated score >= 0.5893 (shipped target_95)
BANDS = ["b_lt90", "b_90", "b_92", "b_95", "b_98", "b_prod"]

meta = json.load(open(O / "world_matrix_meta.json"))
cur = pd.read_parquet(O / "world_matrix_current.parquet")
titles = meta["coicop_titles"]
residual = set(meta["residual_leaves"])
countries = sorted(meta["country_names"])

# --- leaf universe: deep leaves of the COICOP tree, same rule as the EAP matrix
allcodes = sorted(titles)
deep = []
for c in allcodes:
    d = c.count(".") + 1
    if d == 5:
        deep.append(c)
    elif d == 4 and not any(x.startswith(c + ".") for x in allcodes):
        deep.append(c)
deep = sorted(set(deep) - residual)
print("leaf universe %d deep leaves (residual %d excluded)" % (len(deep), len(residual)))
print("countries %d   filled cells %d" % (len(countries), len(cur)))

filled = set(zip(cur.coicop_code, cur.country))
uni = pd.MultiIndex.from_product(
    [deep, countries], names=["coicop", "country"]
).to_frame(index=False)
uni["filled"] = [(c, k) in filled for c, k in zip(uni.coicop, uni.country)]
print("addressable cells %d  filled %d (%.1f%%)"
      % (len(uni), uni.filled.sum(), 100 * uni.filled.mean()))

# --- census -> candidate counts + acceptance at the shipped tau
cen = pd.read_parquet(O / "candidate_census.parquet")
b = cen.pivot_table(index=["country", "proposed_leaf"], columns="band", values="n",
                    aggfunc="sum", fill_value=0, observed=True).reset_index()
for col in BANDS:
    if col not in b:
        b[col] = 0
b["cand"] = b[BANDS].sum(axis=1)
b["acc95"] = b[ACC].sum(axis=1)
b = b.rename(columns={"proposed_leaf": "coicop"})[["country", "coicop", "cand", "acc95"]]

T = uni.merge(b, on=["country", "coicop"], how="left").fillna({"cand": 0, "acc95": 0})
T["cand"] = T.cand.astype(int)
T["acc95"] = T.acc95.astype(int)

def bucket(cand, acc):
    if cand == 0:
        return "A_no_candidates"
    if acc == 0:
        return "B_classifier_blocked"
    return "C_accepted_but_unpublished"

G = T[~T.filled].copy()
G["bucket"] = [bucket(c, a) for c, a in zip(G.cand, G.acc95)]
print("\n--- world gap triage (shipped tau 0.5893) ---")
for k, v in G.bucket.value_counts().items():
    print("%-30s %8d  %6.1f%%" % (k, v, 100 * v / len(G)))
print("%-30s %8d" % ("TOTAL gaps", len(G)))

T.to_parquet(O / "world_triage.parquet", index=False)
G.to_parquet(O / "world_triage_gaps.parquet", index=False)

# --- sourcing depth: is a country's gap a labelling problem or a sourcing problem?
per = T.groupby("country").agg(filled=("filled", "sum"), cand=("cand", "sum")).reset_index()
per = per.sort_values("filled")
print("\ncountry breadth (deep leaves filled), quantiles:")
print(per.filled.describe(percentiles=[.1, .25, .5, .75, .9]).to_string())
per.to_csv(O / "world_country_breadth.csv", index=False)
