"""One pass over the prediction shards: census by (country, parent_pred, band).

Sizes how many gap cells sibling mining can actually reach: a cell can be mined
whenever the leaf's COICOP parent family has volume in that country, even when
the model has never proposed the leaf itself there (bucket A).
"""
import glob, pathlib, time
import pandas as pd

SH = sorted(glob.glob("/home/jeronimoluza/po/data/prices/enrich/_hierlex_pred/"
                      "hierlex_select_v1_20260908/pred_*.parquet"))
O = pathlib.Path("outputs")
EDGES = [0.0, 0.0730, 0.1713, 0.5893, 0.9376, 0.9437, 1.01]
LBL = ["b_lt90", "b_90", "b_92", "b_95", "b_98", "b_prod"]
COLS = ["country", "parent_pred", "calibrated_correctness_score"]

t0 = time.time()
parts = []
for k, f in enumerate(SH):
    d = pd.read_parquet(f, columns=COLS)
    d = d[d.parent_pred.notna()]
    d["band"] = pd.cut(d.calibrated_correctness_score, bins=EDGES, labels=LBL,
                       right=False, include_lowest=True)
    parts.append(d.groupby(["country", "parent_pred", "band"], observed=True)
                 .size().rename("n").reset_index())
    if (k + 1) % 64 == 0:
        print("  %d/%d  %.0fs" % (k + 1, len(SH), time.time() - t0), flush=True)

C = (pd.concat(parts).groupby(["country", "parent_pred", "band"], observed=True)
     .n.sum().reset_index())
C.to_parquet(O / "parent_census.parquet", index=False)
print("parent census %d rows, %d countries, %d parents, %.0fs"
      % (len(C), C.country.nunique(), C.parent_pred.nunique(), time.time() - t0))
