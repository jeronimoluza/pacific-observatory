"""Classify every deep leaf: where does its coverage actually fail?

Three failure modes, and only two of them are a labelling problem.
  suppressed  -- real candidate supply worldwide, but the classifier will not
                 emit it: the highest-value labelling target
  patchy      -- published in some countries, blank in others: mine the blanks
  no_supply   -- almost no candidates anywhere: nothing to label, needs sources
"""
import json, pathlib
import pandas as pd

O = pathlib.Path("outputs")
T = pd.read_parquet(O / "world_triage.parquet")
titles = json.load(open(O / "world_matrix_meta.json"))["coicop_titles"]
gold = pd.read_parquet("/home/jeronimoluza/po/data/prices/enrich/gold/gold_labels.parquet",
                       columns=["code"]).code.value_counts()

L = T.groupby("coicop").agg(cells=("filled", "size"), fill=("filled", "sum"),
                            cand=("cand", "sum"), acc=("acc95", "sum")).reset_index()
L["fill_rate"] = L.fill / L.cells
L["acc_rate"] = L.acc / L.cand.replace(0, pd.NA)
L["gold"] = L.coicop.map(gold).fillna(0).astype(int)
L["title"] = L.coicop.map(titles)

def mode(r):
    if r.cand < 500:
        return "no_supply"
    if r.fill_rate < 0.25:
        return "suppressed"
    return "patchy"

L["mode"] = L.apply(mode, axis=1)
print(L.groupby("mode").agg(leaves=("coicop", "size"), med_fill=("fill_rate", "median"),
                            med_cand=("cand", "median"), med_acc=("acc_rate", "median"),
                            med_gold=("gold", "median")).to_string())

print("\n--- suppressed leaves: supply exists, coverage does not ---")
s = L[L["mode"] == "suppressed"].sort_values("cand", ascending=False)
print(s[["coicop", "title", "fill", "cand", "acc_rate", "gold"]].head(20).to_string(index=False))
print("(%d suppressed leaves, %d candidate rows, median gold %d)"
      % (len(s), s.cand.sum(), int(s.gold.median())))

print("\n--- no_supply leaves: nothing to label, this is the sourcing brief ---")
n = L[L["mode"] == "no_supply"].sort_values("cand")
print(n[["coicop", "title", "fill", "cand", "gold"]].head(15).to_string(index=False))
print("(%d leaves)" % len(n))

L.sort_values(["mode", "cand"], ascending=[True, False]).to_csv(O / "world_leaf_modes.csv", index=False)
