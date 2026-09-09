import pandas as pd
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
c=pd.read_parquet(BASE+'/candidate_census.parquet')
glob_leaf=c.groupby('proposed_leaf').n.sum().rename('leaf_global_pred')
gp=pd.read_parquet(BASE+'/gap_triage_gaps.parquet')
gp=gp.merge(glob_leaf,left_on='coicop',right_index=True,how='left')
gp['leaf_global_pred']=gp.leaf_global_pred.fillna(0).astype(int)

A=gp[gp.bucket=='A_no_candidates']
print('=== BUCKET A (1203 cells) split by whether the model EVER emits that leaf ===')
bins=[-1,0,99,999,9999,10**9]
lbl=['never (0)','1-99','100-999','1k-10k','10k+']
A2=A.assign(band=pd.cut(A.leaf_global_pred,bins=bins,labels=lbl))
t=A2.groupby('band',observed=True).agg(cells=('coicop','size'),leaves=('coicop','nunique'))
print(t.to_string())
print()
print('=== leaves the model NEVER emits anywhere (model-blind) ===')
blind=sorted(A[A.leaf_global_pred==0][['coicop','leaf_name']].drop_duplicates().itertuples(index=False))
print('count:',len(blind))
for co,nm in blind[:40]: print(f'  {co:10s} {nm[:60]}')
print()
print('=== gold-label starvation for gap leaves ===')
gl=gp.groupby(['coicop','leaf_name']).agg(gold_global=('gold_global','max'),
     gap_cells=('coicop','size'), cand=('cand','sum')).reset_index().sort_values('gold_global')
print('gap leaves with <20 gold labels globally:', (gl.gold_global<20).sum(), 'of', len(gl))
print(gl.head(30).to_string(index=False))
