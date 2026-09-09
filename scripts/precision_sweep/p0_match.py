"""Can gold rows be matched to production observations by (country, name)?

If yes, the go/no-go test uses the REAL pipeline's unit value for every gold
row -- no reimplementation of extract/convert/unit-value, so a discrepancy
cannot be an artifact of my own parser.
"""
import pandas as pd, pyarrow.parquet as pq, numpy as np
from pathlib import Path

OBS = "data/prices/build/global_prices_observations.parquet"
B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")

gold = pd.read_parquet("data/prices/enrich/gold/gold_labels.parquet",
                       columns=["gold_row_id", "product_name", "country", "code", "verdict"])
gold = gold[gold.verdict == "leaf"].drop(columns="verdict")
gold["k"] = gold.country.astype(str) + "\x00" + gold.product_name.astype(str)
want = set(gold.k)
print(f"gold leaf rows {len(gold):,}, distinct (country,name) keys {len(want):,}")

f = pq.ParquetFile(OBS)
cols = ["country", "product_name", "coicop_code", "standard_unit",
        "unit_value_local", "pricing_basis", "qa_status", "mass_source"]
hits = []
for i in range(f.metadata.num_row_groups):
    d = f.read_row_group(i, columns=cols).to_pandas()
    d["k"] = d.country.astype(str) + "\x00" + d.product_name.astype(str)
    d = d[d.k.isin(want)]
    if len(d):
        hits.append(d.drop(columns=["product_name"]))
    print(f"  rg {i+1}/{f.metadata.num_row_groups}: kept {len(d):,}", flush=True)

obs = pd.concat(hits, ignore_index=True)
print(f"\nmatched production rows: {len(obs):,}")
print(f"distinct gold keys matched: {obs.k.nunique():,} "
      f"({obs.k.nunique()/len(want):.1%} of gold keys)")

pos = obs[obs.unit_value_local.notna() & (obs.unit_value_local > 0)]
print(f"  with a positive unit_value_local: {pos.k.nunique():,} keys "
      f"({pos.k.nunique()/len(want):.1%})")
print(f"  qa_status of matched rows:")
for s, n in obs.qa_status.value_counts().head(6).items():
    print(f"    {s:<24} {n:>9,}")

# One row per gold key: median unit value, modal unit.
agg = (pos.groupby("k")
          .agg(uv=("unit_value_local", "median"),
               unit=("standard_unit", lambda s: s.mode().iat[0] if len(s.mode()) else None),
               basis=("pricing_basis", lambda s: s.mode().iat[0] if len(s.mode()) else None),
               n_obs=("unit_value_local", "size")))
print(f"\ncollapsed to {len(agg):,} gold keys with a usable unit value")

g = gold.set_index("k").join(agg, how="inner")
fb = g.code.astype(str).str.startswith(("01.", "02."))
print(f"  food & beverage among them: {fb.sum():,}")
print(f"  units: {dict(g.unit.value_counts().head(6))}")
g.reset_index().to_parquet("/tmp/gold_matched_uv.parquet", index=False)
print("\nwrote /tmp/gold_matched_uv.parquet")
