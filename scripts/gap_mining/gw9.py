"""Select the world label-addressable cells and cut the candidate pool to them.

Two ways a gap earns a place in the pack:
  suppressed leaf -- the leaf has real candidate supply worldwide and is still
                     published almost nowhere, so every gap on it is in scope
  anomalous cell  -- the leaf is published for >=25% of the countries in this
                     region, so this country's blank is a pipeline failure
Everything else is either a quantity-parser problem (bucket C) or a genuine
absence of supply, and neither is fixed by labelling.
"""
import json, pathlib
import pandas as pd

O = pathlib.Path("outputs")
SCORE_FLOOR = 0.15  # below this the model is confident it is something else

G = pd.read_parquet(O / "world_gaps_reach.parquet")
L = pd.read_csv(O / "world_leaf_modes.csv")
C = pd.read_parquet(O / "world_candidate_pool.parquet")
titles = json.load(open(O / "world_matrix_meta.json"))["coicop_titles"]

mode = dict(zip(L.coicop, L["mode"]))
G["mode"] = G.coicop.map(mode)
G["in_scope"] = (
    G.reachable
    & G.bucket.isin(["A_no_candidates", "B_classifier_blocked"])
    & ((G["mode"] == "suppressed") | (G.anomalous & (G["mode"] == "patchy")))
)
T = G[G.in_scope]
print("in-scope cells %d  countries %d  leaves %d" % (len(T), T.country.nunique(), T.coicop.nunique()))
print(T.groupby(["mode", "bucket"]).size().to_string())

keep = set(zip(T.country, T.coicop))
C = C[[(c, t) in keep for c, t in zip(C.country, C.target)]]
print("\npool after cell filter: %d" % len(C))
C = C[C.score >= SCORE_FLOOR]
print("pool after score floor %.2f: %d rows, %d cells"
      % (SCORE_FLOOR, len(C), C.groupby(["country", "target"]).ngroups))

C["tname"] = C.target.map(titles)
C.to_parquet(O / "world_pool_scoped.parquet", index=False)
T.to_parquet(O / "world_target_cells.parquet", index=False)

pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 58)
for co in ["nigeria", "brazil", "india", "japan", "france", "kazakhstan", "fiji"]:
    s = C[C.country == co]
    if s.empty:
        continue
    print("\n--- %s (%d rows) ---" % (co, len(s)))
    print(s.sample(min(5, len(s)), random_state=3)[["name", "tname", "score", "reason"]].to_string(index=False))
