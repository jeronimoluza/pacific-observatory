import pandas as pd, numpy as np
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
M=pd.read_parquet(BASE+'/gap_triage_full.parquet')
gp=M[(M.status=='gap')&(M.obs>0)&(M.obs_trusted==0)][['country','coicop']]
key=set(map(tuple,gp.values))
print('cells with obs but zero trusted:',len(key))
d=pd.read_parquet('/home/jeronimoluza/po/data/prices/build/global_prices_observations.parquet',
   columns=['coicop_code','country','qa_status'])
d=d[[ (c,l) in key for c,l in zip(d.country,d.coicop_code)]]
print('observations in those cells:',len(d))
t=d.qa_status.value_counts()
print('\n=== which QA status kills them ===')
for k,v in t.items(): print(f'  {k:28s} {v:8d}  ({v/len(d):6.1%})')
