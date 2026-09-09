"""Turn an enriched label pack into gold_v5 labeling batches.

Ids start well above the highest gv5 id in the consolidated gold so a gap-fill
round can be merged back without colliding with any existing row.
"""
import argparse, pathlib
import pandas as pd

COLS = ["gold_row_id", "product_name_original", "country", "source", "channel",
        "category", "declared_coicop_codes", "price"]

ap = argparse.ArgumentParser()
ap.add_argument("--pack", required=True)
ap.add_argument("--out-dir", required=True)
ap.add_argument("--start-id", type=int, default=300000)
ap.add_argument("--per-batch", type=int, default=150)
ap.add_argument("--start-batch", type=int, default=1)
a = ap.parse_args()

P = pd.read_parquet(a.pack).reset_index(drop=True)
P["gold_row_id"] = ["gv5-%06d" % (a.start_id + i) for i in range(len(P))]
for c in COLS:
    if c not in P:
        P[c] = ""
B = P[COLS].copy()

out = pathlib.Path(a.out_dir)
out.mkdir(parents=True, exist_ok=True)
n = 0
for i in range(0, len(B), a.per_batch):
    idx = a.start_batch + n
    B.iloc[i : i + a.per_batch].to_csv(out / ("gold_v5_batch_%03d.csv" % idx), index=False)
    n += 1
print("wrote %d batches of <=%d to %s" % (n, a.per_batch, out))
print("ids %s .. %s" % (P.gold_row_id.iloc[0], P.gold_row_id.iloc[-1]))

# keep the mapping back to what each row was mined for
P.to_parquet(out.parent / "manifest.parquet", index=False)
print("manifest ->", out.parent / "manifest.parquet")
