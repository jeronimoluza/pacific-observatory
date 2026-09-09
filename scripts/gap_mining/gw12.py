"""Split the world pack into two halves that are equally useful.

Alternating within each (country, parent family) stratum keeps every country and
every COICOP family represented in both halves in the same proportion, so
whoever labels either half sees the same coverage problem.
"""
import pathlib
import pandas as pd

O = pathlib.Path("outputs")
P = pd.read_csv(O / "label_pack_world_20260909.csv")
P = P.sort_values(["country", "parent_family", "score"], ascending=[True, True, False])
P["_i"] = P.groupby(["country", "parent_family"]).cumcount()
P["half"] = P._i.mod(2).map({0: "A_internal", 1: "B_william"})

A = P[P.half == "A_internal"].drop(columns=["_i", "half"])
B = P[P.half == "B_william"].drop(columns=["_i", "half"])
A.to_csv(O / "label_pack_world_20260909_half_A_internal.csv", index=False)
B.to_csv(O / "label_pack_world_20260909_half_B_william.csv", index=False)

for n, d in [("A internal", A), ("B william", B)]:
    print("%-11s %6d rows  %3d countries  %2d families  median score %.3f"
          % (n, len(d), d.country.nunique(), d.parent_family.nunique(), d.score.median()))

chk = (P.groupby(["half", "country"]).size().unstack(0).fillna(0))
chk["imbalance"] = (chk.A_internal - chk.B_william).abs()
print("\nmax per-country imbalance: %d rows" % chk.imbalance.max())
