"""Mine the world label-addressable frontier.

Targets every gap cell that labelling can plausibly move: bucket B (candidates
exist, all rejected) and bucket A (model never proposes the leaf there) where
the COICOP parent family still has rejected rows in that country. Bucket C is
excluded on purpose -- those cells classify fine and die in the quantity
parser, so labels cannot touch them.

Two sources, both restricted to rows still rejected at the shipped target_95
tau, so nothing already flowing through the pipeline is re-labelled:
  uncertainty -- the model proposed the exact target leaf and was rejected
  sibling     -- the row sits in the target leaf's parent family in-country
"""
import glob, json, pathlib, time
import pandas as pd

SH = sorted(glob.glob("/home/jeronimoluza/po/data/prices/enrich/_hierlex_pred/"
                      "hierlex_select_v1_20260908/pred_*.parquet"))
O = pathlib.Path("outputs")
TAU = 0.5893453359603882  # shipped target_95 operating point
COLS = ["name", "country", "proposed_leaf", "parent_pred",
        "calibrated_correctness_score", "script"]

G = pd.read_parquet(O / "world_gaps_reach.parquet")
T = G[G.reachable & G.bucket.isin(["A_no_candidates", "B_classifier_blocked"])]
print("target cells %d  (A %d, B %d)  countries %d  leaves %d"
      % (len(T), (T.bucket == "A_no_candidates").sum(),
         (T.bucket == "B_classifier_blocked").sum(),
         T.country.nunique(), T.coicop.nunique()))

want_par = {}   # (country, parent) -> set of target leaves
want_leaf = {}  # (country, leaf)   -> bucket
for co, ct, pa, bu in zip(T.coicop, T.country, T.parent, T.bucket):
    want_par.setdefault((ct, pa), set()).add(co)
    want_leaf[(ct, co)] = bu
ckeys = set(T.country)
pkeys = set(T.parent)
lkeys = set(T.coicop)

t0 = time.time()
U, S = [], []
for k, f in enumerate(SH):
    d = pd.read_parquet(f, columns=COLS)
    d = d[(d.calibrated_correctness_score < TAU) & d.country.isin(ckeys)]
    if d.empty:
        continue
    # uncertainty: proposed the exact target leaf in a target country
    u = d[d.proposed_leaf.isin(lkeys)]
    if not u.empty:
        u = u[[(c, p) in want_leaf for c, p in zip(u.country, u.proposed_leaf)]]
        if not u.empty:
            U.append(u)
    # sibling: same parent family, in a country that needs a leaf under it
    s = d[d.parent_pred.isin(pkeys)]
    if not s.empty:
        s = s[[(c, p) in want_par for c, p in zip(s.country, s.parent_pred)]]
        if not s.empty:
            S.append(s)
    if (k + 1) % 64 == 0:
        print("  %d/%d  %.0fs" % (k + 1, len(SH), time.time() - t0), flush=True)

U = pd.concat(U) if U else pd.DataFrame(columns=COLS)
S = pd.concat(S) if S else pd.DataFrame(columns=COLS)
print("raw: uncertainty %d, sibling %d  (%.0fs)" % (len(U), len(S), time.time() - t0))

U = U.assign(target=U.proposed_leaf, reason="uncertainty")
S = S.assign(reason="sibling")
S["target"] = [sorted(want_par[(c, p)]) for c, p in zip(S.country, S.parent_pred)]
S = S.explode("target")

C = pd.concat([U, S], ignore_index=True)
C = C.rename(columns={"calibrated_correctness_score": "score",
                      "proposed_leaf": "current_pred"})
C["bucket"] = [want_leaf.get((c, t), "") for c, t in zip(C.country, C.target)]
C = C[C.bucket != ""]
C["src_rank"] = C.reason.map({"uncertainty": 0, "sibling": 1})
C = C.sort_values("src_rank").drop_duplicates(subset=["name", "country", "target"])
print("mined pool: %d rows, %d cells, %d countries"
      % (len(C), C.groupby(["country", "target"]).ngroups, C.country.nunique()))
C.to_parquet(O / "world_candidate_pool.parquet", index=False)
