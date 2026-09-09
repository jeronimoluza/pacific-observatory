import json, pathlib
import pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 62)
O = pathlib.Path("outputs")
titles = json.load(open(O / "world_matrix_meta.json"))["coicop_titles"]
C = pd.read_parquet(O / "world_candidate_pool.parquet")
C["tname"] = C.target.map(titles)
print("scripts:"); print(C.script.value_counts().head(8).to_string())
print("\nregions/countries top+bottom:")
vc = C.country.value_counts()
print(vc.head(6).to_string()); print("..."); print(vc.tail(6).to_string())
print("\nper-cell pool size:"); print(C.groupby(["country","target"]).size().describe(percentiles=[.5,.75,.9]).to_string())
for co in ["nigeria","brazil","india","japan","france","kazakhstan"]:
    s = C[C.country == co]
    if s.empty: continue
    print("\n--- %s (%d rows) ---" % (co, len(s)))
    print(s.sample(min(6, len(s)), random_state=1)[["name","tname","score","reason"]].to_string(index=False))
