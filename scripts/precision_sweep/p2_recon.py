"""Reconcile: the leaf-pair gap says 1.84x, the row-level AUC said 0.4995.

Both cannot be right. The pair statistic asks how far apart two LEAVES sell;
the AUC asked whether a ROW looks anomalous in the cell it landed in. This
measures the row-level quantity the pair statistic predicts, on the same rows
the AUC used, so the disagreement has to resolve.
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

OBS = "data/prices/build/global_prices_observations.parquet"

m = pd.read_parquet("/tmp/p0_joined.parquet")
sub = m[m.below].copy()
print("below-tau matched rows: %s   wrong: %s"
      % (format(len(sub), ","), format(int(sub.wrong.sum()), ",")))

# Cell medians in LOCAL currency, to match unit_value_local in the joined file.
f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_local", "qa_status"]
parts = []
for i in range(f.metadata.num_row_groups):
    d = f.read_row_group(i, columns=cols).to_pandas()
    d = d[d.unit_value_local.notna() & (d.unit_value_local > 0)]
    parts.append(d)
obs = pd.concat(parts, ignore_index=True)
del parts
cells = (obs.groupby(["coicop_code", "country", "standard_unit"], observed=True)
            .unit_value_local.agg(cmed="median", cn="size").reset_index())
cells = cells[cells.cn >= 3]
for c in ("coicop_code", "country", "standard_unit"):
    cells[c] = cells[c].astype(str)
print("cells n>=3: %s" % format(len(cells), ","))

for c in ("assigned", "country", "unit"):
    sub[c] = sub[c].astype(str)
j = sub.merge(cells.rename(columns={"coicop_code": "assigned", "standard_unit": "unit"}),
              on=["assigned", "country", "unit"], how="left")
j["lr"] = np.log(j.uv / j.cmed)
ok = j[j.lr.notna() & np.isfinite(j.lr)]
print("rows placed against their assigned cell: %s (%.1f%%)"
      % (format(len(ok), ","), len(ok) / len(j) * 100))

print("\nDISTANCE FROM THE ASSIGNED CELL'S MEDIAN")
print("%-9s %8s %9s %8s %8s" % ("group", "n", "med ratio", ">2x", ">5x"))
for lab, d in (("wrong", ok[ok.wrong]), ("correct", ok[~ok.wrong])):
    a = d.lr.abs()
    print("%-9s %8s %8.2fx %7.1f%% %7.1f%%" % (
        lab, format(len(d), ","), float(np.exp(a.median())),
        (a > np.log(2)).mean() * 100, (a > np.log(5)).mean() * 100))

# AUC of |log ratio| as a discriminator -- the quantity the gate actually uses.
from sklearn.metrics import roc_auc_score
y = ok.wrong.astype(int).to_numpy()
print("\nAUC of |log ratio to cell median| vs wrong : %.4f"
      % roc_auc_score(y, ok.lr.abs().to_numpy()))
z = ok[ok.absz.notna()]
if len(z):
    print("AUC of production |uv_robust_z|        vs wrong : %.4f  (n=%s)"
          % (roc_auc_score(z.wrong.astype(int), z.absz.abs()), format(len(z), ",")))
print("rows where production left uv_robust_z NULL: %s (%.1f%%)"
      % (format(int(ok.absz.isna().sum()), ","), ok.absz.isna().mean() * 100))

# If the two AUCs disagree, the cell the z was computed against is the suspect.
print("\ncell size behind each row (production uv_cell_n):")
for lab, d in (("wrong", ok[ok.wrong]), ("correct", ok[~ok.wrong])):
    print("  %-8s median %8s   share n<10: %5.1f%%"
          % (lab, format(int(d.cell_n.median()) if d.cell_n.notna().any() else -1, ","),
             (d.cell_n < 10).mean() * 100))
