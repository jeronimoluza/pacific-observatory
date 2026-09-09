import pandas as pd, numpy as np, glob, os, sys, time

SRC='/home/jeronimoluza/po/data/prices/enrich/_hierlex_pred/hierlex_select_v1_20260908'
OUT='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
os.makedirs(OUT, exist_ok=True)

# score bands from the precision-sweep tau curve
EDGES = [0.0, 0.0730, 0.1713, 0.5893, 0.9376, 0.9437, 1.01]
LBL   = ['b_lt90','b_90','b_92','b_95','b_98','b_prod']

files = sorted(glob.glob(os.path.join(SRC,'pred_*.parquet')))
print('shards', len(files), flush=True)

parts=[]
t0=time.time()
for i,f in enumerate(files):
    d = pd.read_parquet(f, columns=['country','proposed_leaf','calibrated_correctness_score','accepted','is_fallback'])
    d = d[d.proposed_leaf.notna()]
    d['band'] = pd.cut(d.calibrated_correctness_score, bins=EDGES, labels=LBL, right=False, include_lowest=True)
    g = (d.groupby(['country','proposed_leaf','band'], observed=True)
           .agg(n=('accepted','size'),
                n_acc=('accepted','sum'),
                n_fb=('is_fallback','sum'))
           .reset_index())
    parts.append(g)
    if (i+1) % 32 == 0:
        parts=[pd.concat(parts).groupby(['country','proposed_leaf','band'],observed=True).sum().reset_index()]
        print(f'  {i+1}/{len(files)} rows={len(parts[0])} {time.time()-t0:.0f}s', flush=True)

agg = (pd.concat(parts).groupby(['country','proposed_leaf','band'],observed=True).sum().reset_index())
agg.to_parquet(os.path.join(OUT,'candidate_census.parquet'), index=False)
print('census rows', len(agg))
print('total predicted rows', int(agg.n.sum()))
print('distinct countries', agg.country.nunique())
print('distinct leaves', agg.proposed_leaf.nunique())
print(sorted(agg.country.unique())[:80])
