"""World leaf profile: gaps, candidates, acceptance, gold. Select target leaves."""
import json, pathlib
import pandas as pd
from scipy.stats import spearmanr

O = pathlib.Path("outputs")
GOLD = pathlib.Path("/home/jeronimoluza/po/data/prices/enrich/gold/gold_labels.parquet")

T = pd.read_parquet(O / "world_triage.parquet")
G = pd.read_parquet(O / "world_triage_gaps.parquet")
titles = json.load(open(O / "world_matrix_meta.json"))["coicop_titles"]

g = pd.read_parquet(GOLD, columns=["code"])
gold = g.code.value_counts().rename("gold")

L = T.groupby("coicop").agg(
    cells=("filled", "size"), fill=("filled", "sum"), cand=("cand", "sum"),
    acc=("acc95", "sum"),
).reset_index()
L["gaps"] = L.cells - L.fill
L["gap_rate"] = L.gaps / L.cells
L["acc_rate"] = L.acc / L.cand.replace(0, pd.NA)
L["gold"] = L.coicop.map(gold).fillna(0).astype(int)
L["title"] = L.coicop.map(titles)

blk = G[G.bucket == "B_classifier_blocked"].groupby("coicop").size().rename("blocked")
L["blocked"] = L.coicop.map(blk).fillna(0).astype(int)

sub = L[L.cand > 0]
rho, p = spearmanr(sub.gold, sub.gap_rate)
print("gold vs gap_rate: rho=%.3f p=%.3g  n=%d" % (rho, p, len(sub)))

# the causal band replicated at world scale
sub = sub.copy()
sub["vq"] = pd.qcut(sub.cand, 4, labels=["Q1", "Q2", "Q3", "Q4"])
print("\nacceptance by gold, within candidate-volume quartile:")
for q, s in sub.groupby("vq", observed=True):
    if len(s) < 8:
        continue
    s = s.assign(gq=pd.qcut(s.gold, 2, labels=["lo", "hi"], duplicates="drop"))
    m = s.groupby("gq", observed=True).acc_rate.mean()
    r, pp = spearmanr(s.gold, s.acc_rate)
    print("  %s  n=%3d  med_cand=%8.0f  lo=%.3f hi=%.3f  rho=%.3f p=%.4f"
          % (q, len(s), s.cand.median(), m.get("lo", float("nan")),
             m.get("hi", float("nan")), r, pp))

# --- target leaves: classifier-limited, gold-starved, enough supply to work with
tgt = L[(L.blocked >= 3) & (L.gold < 250) & (L.cand >= 200) & (L.acc_rate < 0.45)].copy()
tgt = tgt.sort_values("blocked", ascending=False)
print("\ntarget leaves: %d   blocked cells covered: %d of %d"
      % (len(tgt), tgt.blocked.sum(), int(L.blocked.sum())))
print(tgt[["coicop", "title", "gaps", "blocked", "cand", "acc_rate", "gold"]]
      .head(25).to_string(index=False))

L.sort_values("blocked", ascending=False).to_csv(O / "world_leaf_profile.csv", index=False)
tgt.to_csv(O / "world_target_leaves.csv", index=False)
