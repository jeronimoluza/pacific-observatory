"""Split world gaps into anomalous (label-addressable) vs structural (sourcing).

A gap is *anomalous* when the same leaf is published for a meaningful share of
the other countries in its region: the product is demonstrably sold and
scrapeable nearby, so this country's blank is a pipeline failure. A gap is
*structural* when the leaf is blank across the region -- no amount of labelling
invents a market, and that set is the brief for new specialised sources.
"""
import json, pathlib
import yaml
import pandas as pd

O = pathlib.Path("outputs")
REG = pathlib.Path("/home/jeronimoluza/po-worktrees/gap-mining/src/configs/regions.yaml")
SHARE = 0.25  # a leaf filled for >=25% of a region's countries is "normal there"

topo = yaml.safe_load(REG.read_text()) or {}
of_country = {}
for key, meta in topo.items():
    for sub in (meta.get("subregions") or {}).values():
        for slug in sub.get("countries") or []:
            of_country[slug] = key

G = pd.read_parquet(O / "world_gaps_reach.parquet")
T = pd.read_parquet(O / "world_triage.parquet")
titles = json.load(open(O / "world_matrix_meta.json"))["coicop_titles"]

T["region"] = T.country.map(of_country).fillna("unassigned")
G["region"] = G.country.map(of_country).fillna("unassigned")
print("countries without a region: %d" % T[T.region == "unassigned"].country.nunique())

rf = (T.groupby(["region", "coicop"])
        .agg(n=("filled", "size"), f=("filled", "sum")).reset_index())
rf["region_share"] = rf.f / rf.n
G = G.merge(rf[["region", "coicop", "region_share"]], on=["region", "coicop"], how="left")
G["anomalous"] = G.region_share >= SHARE

print("\nworld gaps %d" % len(G))
x = G.groupby(["bucket", "anomalous"]).size().unstack(fill_value=0)
x.columns = ["structural", "anomalous"]
print(x.to_string())
print("\nanomalous + sibling-reachable, labelling-relevant buckets (A/B):")
LAB = G[G.anomalous & G.reachable & G.bucket.isin(["A_no_candidates", "B_classifier_blocked"])]
print("  cells %d  countries %d  leaves %d  pool %d"
      % (len(LAB), LAB.country.nunique(), LAB.coicop.nunique(), LAB.fam_rej.sum()))

# --- the sourcing brief: structural gaps, ranked by how many countries miss them
ST = G[~G.anomalous]
src = (ST.groupby("coicop").agg(missing_cells=("country", "size"),
                                regions=("region", "nunique")).reset_index())
src["title"] = src.coicop.map(titles)
src = src.sort_values("missing_cells", ascending=False)
src.to_csv(O / "world_sourcing_brief_leaves.csv", index=False)
srcc = (ST.groupby("country").size().rename("structural_gaps").reset_index()
          .sort_values("structural_gaps", ascending=False))
srcc.to_csv(O / "world_sourcing_brief_countries.csv", index=False)
print("\nsourcing brief -- leaves structurally missing in the most countries:")
print(src.head(10)[["coicop", "title", "missing_cells", "regions"]].to_string(index=False))

G.to_parquet(O / "world_gaps_reach.parquet", index=False)
