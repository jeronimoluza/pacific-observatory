"""Attach the retailer context the gold-labeling prompt expects to a label pack.

The pack carries only (name, country) because that is all the prediction shards
hold. `products_input` has the source, channel, retailer category, declared
codes and price, so one filtered scan puts each candidate back in its context.
"""
import argparse, pathlib
import pandas as pd
import pyarrow.parquet as pq

PI = "/home/jeronimoluza/po/data/prices/enrich/products_input.parquet"
COLS = ["product_name_original", "country", "source", "channel", "category",
        "declared_coicop_codes", "price", "observation_date"]

ap = argparse.ArgumentParser()
ap.add_argument("--pack", required=True)
ap.add_argument("--name-col", default="product_name")
ap.add_argument("--out", required=True)
a = ap.parse_args()

P = pd.read_csv(a.pack) if a.pack.endswith(".csv") else pd.read_parquet(a.pack)
P = P.rename(columns={a.name_col: "_name"})
keys = set(zip(P["_name"].astype(str), P.country.astype(str)))
names = set(P["_name"].astype(str))
print("pack %d rows, %d distinct (name,country)" % (len(P), len(keys)))

f = pq.ParquetFile(PI)
hits = []
for i in range(f.num_row_groups):
    d = f.read_row_group(i, columns=COLS).to_pandas()
    d = d[d.product_name_original.isin(names)]
    if d.empty:
        continue
    d = d[[(n, c) in keys for n, c in zip(d.product_name_original, d.country)]]
    if not d.empty:
        hits.append(d)
    if (i + 1) % 40 == 0:
        print("  rg %d/%d, hits %d" % (i + 1, f.num_row_groups,
                                       sum(len(h) for h in hits)), flush=True)

H = pd.concat(hits, ignore_index=True) if hits else pd.DataFrame(columns=COLS)
H["observation_date"] = pd.to_datetime(H.observation_date, errors="coerce", utc=True)
H = (H.sort_values("observation_date", ascending=False)
       .drop_duplicates(subset=["product_name_original", "country"]))
print("context rows matched: %d" % len(H))

M = P.merge(H, left_on=["_name", "country"], right_on=["product_name_original", "country"],
            how="left")
M["product_name_original"] = M.product_name_original.fillna(M["_name"])
print("matched %d of %d (%.1f%%)" % (M.source.notna().sum(), len(M),
                                     100 * M.source.notna().mean()))
M.drop(columns=["_name"]).to_parquet(a.out, index=False)
print("wrote", a.out)
