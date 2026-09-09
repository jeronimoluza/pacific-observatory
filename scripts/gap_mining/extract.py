import pandas as pd, numpy as np, glob, os, time
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
SRC='/home/jeronimoluza/po/data/prices/enrich/_hierlex_pred/hierlex_select_v1_20260908'

M=pd.read_parquet(BASE+'/gap_triage_full.parquet')
L=(M.groupby(['coicop','leaf_name'])
    .agg(gaps=('status',lambda s:(s=='gap').sum()),gold=('gold_global','max'),
         cand=('cand','sum'),cand_acc=('cand_acc','sum')).reset_index())
L['acc_rate']=np.where(L.cand>0,L.cand_acc/L.cand,np.nan)
# CLASSIFIER-LIMITED: real supply, thin gold, model won't commit
tgt=L[(L.gaps>=8)&(L.gold<250)&(L.cand>=200)&(L.acc_rate<0.45)].copy()
tgt=tgt.sort_values(['gaps','acc_rate'],ascending=[False,True])
tgt.to_csv(BASE+'/target_leaves.csv',index=False)
print(f'CLASSIFIER-LIMITED target leaves: {len(tgt)} covering {tgt.gaps.sum()} gap cells')
print(tgt[['coicop','leaf_name','gaps','gold','cand','acc_rate']].head(30).to_string(index=False))

leaves=set(tgt.coicop)
gapcells=M[(M.status=='gap')&(M.coicop.isin(leaves))][['country','coicop']].drop_duplicates()
gset=set(map(tuple,gapcells.values))
print(f'\ntarget gap cells: {len(gset)}')

files=sorted(glob.glob(os.path.join(SRC,'pred_*.parquet')))
keep=[]; t0=time.time()
for i,f in enumerate(files):
    d=pd.read_parquet(f,columns=['name','country','proposed_leaf','calibrated_correctness_score','accepted','is_fallback','script'])
    d=d[d.proposed_leaf.isin(leaves)]
    if len(d)==0: continue
    d=d[[ (c,l) in gset for c,l in zip(d.country,d.proposed_leaf)]]
    if len(d): keep.append(d)
    if (i+1)%64==0: print(f'  {i+1}/{len(files)} kept={sum(len(k) for k in keep)} {time.time()-t0:.0f}s',flush=True)
C=pd.concat(keep,ignore_index=True) if keep else pd.DataFrame()
print('\ncandidate rows in target gap cells:',len(C))
C=C.rename(columns={'proposed_leaf':'coicop','calibrated_correctness_score':'score'})
C=C.merge(tgt[['coicop','leaf_name']],on='coicop',how='left')
C.to_parquet(BASE+'/candidates_raw.parquet',index=False)
print(C.groupby('accepted').size().to_string())
print('\nby country (top 15):')
print(C.groupby('country').size().sort_values(ascending=False).head(15).to_string())
