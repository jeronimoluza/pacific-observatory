"""Build the world gap-fill label pack.

One row per (product, country, COICOP parent family). The target leaf is a hint,
not a claim -- a row earns its place by sitting in a family where that country
is missing leaves, and the labeller assigns the true leaf. Collapsing the
sibling explode this way stops one product consuming several labelling slots.
"""
import json, pathlib
import pandas as pd

O = pathlib.Path("outputs")
TAU = 0.5893453359603882
PER_FAM_COUNTRY = 60   # cap per (country, parent family)
PER_COUNTRY = 1200     # cap per country, so a few deep markets cannot crowd out the rest

C = pd.read_parquet(O / "world_pool_scoped.parquet")
titles = json.load(open(O / "world_matrix_meta.json"))["coicop_titles"]
C["fam"] = C.target.str.rsplit(".", n=1).str[0]

g = (C.sort_values(["src_rank", "target"])
       .groupby(["name", "country", "fam"], as_index=False)
       .agg(candidate_for=("target", lambda s: ";".join(sorted(set(s)))),
            score=("score", "first"), current_pred=("current_pred", "first"),
            script=("script", "first"), reason=("reason", "first"),
            src_rank=("src_rank", "first")))
g["candidate_for_names"] = g.candidate_for.map(
    lambda s: "; ".join(titles.get(c, c) for c in s.split(";")))
g["parent_family"] = g.fam.map(lambda f: titles.get(f, f))
print("collapsed pool: %d rows (%d products)" % (len(g), g.groupby(["name", "country"]).ngroups))

def pick(d, k):
    if len(d) <= k:
        return d
    return (d.assign(_d=(d.score - TAU).abs())
             .sort_values(["src_rank", "_d"]).head(k).drop(columns="_d"))

g = (g.groupby(["country", "fam"], group_keys=False).apply(pick, PER_FAM_COUNTRY)
      .groupby("country", group_keys=False).apply(pick, PER_COUNTRY))
print("after caps: %d rows, %d countries, %d families"
      % (len(g), g.country.nunique(), g.fam.nunique()))

P = g.rename(columns={"name": "product_name"})[
    ["country", "product_name", "parent_family", "candidate_for", "candidate_for_names",
     "current_pred", "score", "script", "reason"]
].sort_values(["country", "parent_family", "score"], ascending=[True, True, False])
P.to_csv(O / "label_pack_world_20260909.csv", index=False)
print("wrote outputs/label_pack_world_20260909.csv")

print("\nscripts:"); print(P.script.value_counts().to_string())
print("\nreason:"); print(P.reason.value_counts().to_string())
vc = P.country.value_counts()
print("\ncountries %d  top: %s" % (len(vc), dict(vc.head(5))))
print("bottom: %s" % dict(vc.tail(5)))
