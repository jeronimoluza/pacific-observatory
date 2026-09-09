"""Extract the world matrix (DATA.current) out of the shipped dashboard."""
import json, re, pathlib
import pandas as pd

H = pathlib.Path("/home/jeronimoluza/po/outputs/prices/global_prices_dashboard.html")
OUT = pathlib.Path("/home/jeronimoluza/po-worktrees/gap-mining/outputs")
OUT.mkdir(parents=True, exist_ok=True)

s = H.read_text(encoding="utf-8", errors="replace")
i = s.index("const DATA = {") + len("const DATA = ")
# brace-match to find the end of the object literal
d = 0
for j in range(i, len(s)):
    if s[j] == "{":
        d += 1
    elif s[j] == "}":
        d -= 1
        if d == 0:
            break
DATA = json.loads(s[i : j + 1])
print("keys:", sorted(DATA.keys()))
cur = pd.DataFrame(DATA["current"])
print("current:", cur.shape, list(cur.columns))
print(cur.head(3).to_string())
print("countries:", len(DATA["country_names"]), "titles:", len(DATA["coicop_titles"]))
print("residual leaves:", len(DATA.get("residual_leaves", [])))
print("regions:", [r["key"] for r in DATA.get("region_cols", [])])
cur.to_parquet(OUT / "world_matrix_current.parquet", index=False)
json.dump(
    {k: DATA[k] for k in ("country_names", "coicop_titles", "region_cols", "residual_leaves", "lookback_days")},
    open(OUT / "world_matrix_meta.json", "w"),
)
