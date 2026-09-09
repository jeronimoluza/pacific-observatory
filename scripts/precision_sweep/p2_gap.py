"""When the model is wrong, how far off is the price of the cell it lands in?

This is failure mode 1 measured directly. Every wrong OOF row carries the leaf
the model proposed and the leaf that was true. If those two leaves sell at the
same price per unit, the misclassification is invisible to any dispersion test
AND harmless to the published median. If they sell at different prices, the row
biases its cell -- and biased contamination is the one thing a median does not
absorb.

No unit-value join is used, so the accept-only selection that makes
gold_matched_uv unrepresentative cannot reach this measurement.
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
OBS = "data/prices/build/global_prices_observations.parquet"

# ---- production cell medians: the price each (leaf, country, unit) sells at ---
f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_usd", "qa_status"]
parts = []
for i in range(f.metadata.num_row_groups):
    d = f.read_row_group(i, columns=cols).to_pandas()
    d = d[(d.qa_status == "trusted") & d.unit_value_usd.notna() & (d.unit_value_usd > 0)]
    parts.append(d.drop(columns=["qa_status"]))
obs = pd.concat(parts, ignore_index=True)
del parts
print("trusted priced rows: %s" % format(len(obs), ","))

cells = (obs.groupby(["coicop_code", "country", "standard_unit"], observed=True)
            .unit_value_usd.agg(med="median", n="size").reset_index())
cells = cells[cells.n >= 3]
for c in ("coicop_code", "country", "standard_unit"):
    cells[c] = cells[c].astype(str)
print("cells with n>=3: %s" % format(len(cells), ","))

# ---- wrong rows, banded -------------------------------------------------------
oof = pd.read_parquet(
    B / "audit/implementation_oof_decisions.parquet",
    columns=["row_pos", "calibrated_correctness_score_oof", "action_correct",
             "proposed_leaf", "gold", "country"])
EDGES = [("at/above tau", 0.9437, 1.01),
         ("98pct band", 0.9376, 0.9437),
         ("95pct band", 0.5893, 0.9376),
         ("92pct band", 0.1713, 0.5893),
         ("90pct band", 0.0730, 0.1713),
         ("below .073", -0.01, 0.0730)]
s = oof["calibrated_correctness_score_oof"]
oof["band"] = None
for lab, lo, hi in EDGES:
    oof.loc[(s >= lo) & (s < hi), "band"] = lab

wrong = oof[~oof.action_correct].copy()
for c in ("proposed_leaf", "gold", "country"):
    wrong[c] = wrong[c].astype(str)
print("wrong rows total: %s" % format(len(wrong), ","))

# ---- price gap between the assigned leaf and the true leaf --------------------
# Same country first; the units where BOTH leaves have a real cell are the only
# places the two prices are comparable at all.
def gaps(w, keys):
    left = w.merge(cells.rename(columns={"coicop_code": "proposed_leaf",
                                         "med": "med_p", "n": "n_p"}),
                   on=keys + ["proposed_leaf"], how="inner")
    both = left.merge(cells.rename(columns={"coicop_code": "gold",
                                            "med": "med_g", "n": "n_g"}),
                      on=keys + ["gold", "standard_unit"], how="inner")
    both["lg"] = np.log(both.med_p / both.med_g)
    return both.groupby("row_pos").lg.median()

g_ctry = gaps(wrong, ["country"])
rest = wrong[~wrong.row_pos.isin(g_ctry.index)]
g_glob = gaps(rest, [])          # pooled across countries as a fallback
gap = pd.concat([g_ctry, g_glob])
wrong["lg"] = wrong.row_pos.map(gap)
cov = wrong.lg.notna().mean()
print("wrong rows with a measurable price gap: %s (%.1f%%)"
      % (format(int(wrong.lg.notna().sum()), ","), cov * 100))

# ---- verdict ------------------------------------------------------------------
hdr = "%-13s %8s %9s %9s %8s %8s %8s" % (
    "band", "wrong", "gap>1.25x", "med|gap|", ">1.5x", ">2x", ">5x")
print("\nHOW WRONG IS A WRONG ROW'S PRICE, by band")
print(hdr)
print("-" * len(hdr))
for lab, _, _ in EDGES:
    w = wrong[(wrong.band == lab) & wrong.lg.notna()]
    if len(w) < 50:
        print("%-13s %8s   (too thin)" % (lab, format(len(w), ",")))
        continue
    a = w.lg.abs()
    print("%-13s %8s %8.1f%% %9.2fx %7.1f%% %7.1f%% %7.1f%%" % (
        lab, format(len(w), ","), (a > np.log(1.25)).mean() * 100,
        float(np.exp(a.median())), (a > np.log(1.5)).mean() * 100,
        (a > np.log(2)).mean() * 100, (a > np.log(5)).mean() * 100))

# Is the bias directional? A median absorbs symmetric noise; it does not absorb
# contamination that lands consistently on one side.
print("\nDIRECTION (a median survives symmetric error, not one-sided error)")
print("%-13s %9s %9s" % ("band", "share up", "mean log"))
for lab, _, _ in EDGES:
    w = wrong[(wrong.band == lab) & wrong.lg.notna()]
    if len(w) < 50:
        continue
    print("%-13s %8.1f%% %9.3f" % (lab, (w.lg > 0).mean() * 100, w.lg.mean()))
