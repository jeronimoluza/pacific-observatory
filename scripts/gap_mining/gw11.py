import pathlib, pandas as pd
pd.set_option("display.width", 240); pd.set_option("display.max_colwidth", 54)
P = pd.read_csv(pathlib.Path("outputs") / "label_pack_world_20260909.csv")
print("rows %d  countries %d" % (len(P), P.country.nunique()))
print("\ntop families:"); print(P.parent_family.value_counts().head(10).to_string())
for co in ["japan", "nigeria", "peru", "morocco", "vietnam", "poland", "fiji", "mongolia"]:
    s = P[P.country == co]
    if s.empty: continue
    print("\n--- %s (%d) ---" % (co, len(s)))
    print(s.sample(min(4, len(s)), random_state=7)[
        ["product_name", "parent_family", "candidate_for_names", "score"]].to_string(index=False))
