# -*- coding: utf-8 -*-
"""Sibling mining: for each gap cell (leaf X, country C), find rows in C that the model
placed in X's PARENT family but not on X - the true active-learning frontier.
Language-agnostic; uses parent_pred which the model already emits."""
import pandas as pd, numpy as np, glob, os, time
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
SRC='/home/jeronimoluza/po/data/prices/enrich/_hierlex_pred/hierlex_select_v1_20260908'

tgt=pd.read_csv(BASE+'/target_leaves.csv')
M=pd.read_parquet(BASE+'/gap_triage_full.parquet')
gaps=M[(M.status=='gap')&(M.coicop.isin(set(tgt.coicop)))]
# parent of a depth-5 leaf 01.1.7.5.5 -> 01.1.7.5
def par(c):
    p=c.split('.'); return '.'.join(p[:-1])
want={}                      # (country, parent) -> set of target leaves
for co,ct in zip(gaps.coicop,gaps.country): want.setdefault((ct,par(co)),set()).add(co)
print('gap cells',len(gaps),'| (country,parent) keys',len(want),flush=True)
pkeys=set(k[1] for k in want); ckeys=set(k[0] for k in want)

files=sorted(glob.glob(os.path.join(SRC,'pred_*.parquet')))
keep=[]; t0=time.time()
for i,f in enumerate(files):
    d=pd.read_parquet(f,columns=['name','country','proposed_leaf','parent_pred','calibrated_correctness_score','accepted','script'])
    d=d[d.country.isin(ckeys)&d.parent_pred.isin(pkeys)]
    if not len(d): continue
    d=d[[ (c,p) in want for c,p in zip(d.country,d.parent_pred)]]
    if len(d): keep.append(d)
    if (i+1)%64==0: print(f'  {i+1}/{len(files)} kept={sum(len(k) for k in keep)} {time.time()-t0:.0f}s',flush=True)

S=pd.concat(keep,ignore_index=True).rename(columns={'calibrated_correctness_score':'score'})
S.to_parquet(BASE+'/sibling_candidates.parquet',index=False)
print('\nsibling candidates:',len(S))
print('  rejected (model unsure in the right family):',int((~S.accepted).sum()))
print('\nby country:'); print(S.groupby('country').size().sort_values(ascending=False).head(28).to_string())
print('\nby parent family:'); print(S.groupby('parent_pred').size().sort_values(ascending=False).head(15).to_string())
