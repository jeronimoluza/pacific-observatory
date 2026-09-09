import pandas as pd, numpy as np
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
M=pd.read_parquet(BASE+'/gap_triage_full.parquet')
L=(M.groupby(['coicop','leaf_name'])
    .agg(cells=('status','size'),gaps=('status',lambda s:(s=='gap').sum()),
         gold=('gold_global','max'),cand=('cand','sum'),cand_acc=('cand_acc','sum'),
         obs=('obs','sum')).reset_index())
L['gap_rate']=L.gaps/L.cells
L['acc_rate']=np.where(L.cand>0,L.cand_acc/L.cand,np.nan)
# label-addressable score: many gaps, low gold, supply in the sweet spot (>=200 candidates)
L['addressable']=(L.gaps>=8)&(L.gold<250)&(L.cand>=200)
T=L[L.addressable].sort_values(['gaps','gold'],ascending=[False,True])
print(f'LABEL-ADDRESSABLE leaves: {len(T)}  (gap cells they cover: {T.gaps.sum()})')
print(T[['coicop','leaf_name','gaps','gold','cand','cand_acc','acc_rate','obs']].head(45).to_string(index=False))
T.to_csv(BASE+'/priority_leaves.csv',index=False)
print()
sup=L[(L.gaps>=8)&(L.cand<200)]
print(f'SUPPLY-LIMITED (gaps>=8 but <200 candidates anywhere): {len(sup)} leaves, {sup.gaps.sum()} gap cells')
print(sup[['coicop','leaf_name','gaps','gold','cand']].head(20).to_string(index=False))
