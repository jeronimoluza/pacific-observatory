"""Can the anchor exist where we actually need it?

The isotone rule needs confident rows IN THE CELL to locate the price. The
cells we are trying to fill are empty precisely because they have none. Measure
it on the real corpus: per (leaf x country x unit), how many rows sit above
production tau versus in the relaxed band?
"""
import pandas as pd, numpy as np, glob, os
from pathlib import Path

TAU_P, TAU95 = 0.9436536386510268, 0.5893
CACHE = Path("data/prices/enrich/cache/decisions_hierlex")
import yaml
topo = yaml.safe_load(Path("src/configs/regions.yaml").read_text()) or {}
eap = {s for r, m in topo.items() if r == "eap"
       for sub in (m.get("subregions") or {}).values()
       for s in (sub.get("countries") or [])}

rows = []
for f in sorted(CACHE.glob("*.parquet")):
    c = f.stem
    if c not in eap:
        continue
    d = pd.read_parquet(f, columns=["leaf_top1", "standard_unit", "gate_score"])
    d = d[d.leaf_top1.notna() & d.standard_unit.notna()]
    d = d[d.leaf_top1.astype(str).str.startswith(("01.", "02."))]
    if not len(d):
        continue
    d["tierA"] = d.gate_score >= TAU_P
    d["tierB"] = (d.gate_score >= TAU95) & (d.gate_score < TAU_P)
    g = d.groupby([d.leaf_top1.astype(str), d.standard_unit.astype(str)]).agg(
        A=("tierA", "sum"), B=("tierB", "sum"), n=("gate_score", "size"))
    g["country"] = c
    rows.append(g.reset_index())
    print(f"  {c:<24} {len(d):>9,} F&B rows, {len(g):>4} cells", flush=True)

cells = pd.concat(rows, ignore_index=True)
cells.columns = ["leaf", "unit", "A", "B", "n", "country"]
print(f"\nEAP F&B cells (leaf x country x unit): {len(cells):,}")

MIN = 3
has_now = cells.A >= MIN
gains = (cells.A + cells.B) >= MIN
new = gains & ~has_now
print(f"\n{'':<38}{'cells':>9}{'share':>9}")
print(f"{'publishable today (tierA >= 3)':<38}{has_now.sum():>9,}{has_now.mean():>9.1%}")
print(f"{'publishable at the 95% target':<38}{gains.sum():>9,}{gains.mean():>9.1%}")
print(f"{'NEWLY created by relaxation':<38}{new.sum():>9,}{new.mean():>9.1%}")

print("\n=== do the NEW cells have an anchor? ===")
nd = cells[new]
print(f"  new cells with ZERO tier-A rows:      {(nd.A == 0).sum():>6,}"
      f"  ({(nd.A == 0).mean():.1%})")
print(f"  new cells with 1-2 tier-A rows:       {nd.A.between(1,2).sum():>6,}"
      f"  ({nd.A.between(1,2).mean():.1%})")
print("\n  -> an anchor needs >=3 confident rows. Cells with 0-2 cannot be")
print("     anchored, so the isotone rule has nothing to measure against.")
anchorable = (nd.A >= 3).sum()
print(f"  new cells that COULD be anchored:      {anchorable:>6,} ({anchorable/len(nd):.1%})")

print("\n=== where the coverage actually comes from ===")
print(f"  extra rows in cells that already publish: "
      f"{cells.loc[has_now,'B'].sum():>10,}")
print(f"  rows in newly-created cells:              "
      f"{cells.loc[new,['A','B']].sum().sum():>10,}")
