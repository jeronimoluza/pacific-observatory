import pandas as pd, numpy as np
from scipy.stats import spearmanr
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
M=pd.read_parquet(BASE+'/gap_triage.parquet')
L=(M.groupby(['coicop','leaf_name'])
     .agg(cells=('status','size'),gaps=('status',lambda s:(s=='gap').sum()),
          gold=('gold_global','max'),cand=('cand','sum'),cand_acc=('cand_acc','sum')).reset_index())
L['gap_rate']=L.gaps/L.cells
L=L[L.cand>0].copy()
L['acc_rate']=L.cand_acc/L.cand
print('leaves with candidates:',len(L))
r,p=spearmanr(L.gold,L.acc_rate)
print(f'\nSpearman(gold, ACCEPTANCE RATE) = {r:.3f} p={p:.2e}')
print('\n=== acceptance rate by gold decile (market volume NOT controlled) ===')
L['gd']=pd.qcut(L.gold,5,labels=['g1 lowest','g2','g3','g4','g5 highest'],duplicates='drop')
print(L.groupby('gd',observed=True).agg(leaves=('coicop','size'),gold_med=('gold','median'),
      cand_med=('cand','median'),acc_rate=('acc_rate','median')).round(3).to_string())

print('\n=== CONTROLLED: acceptance rate by gold, WITHIN candidate-volume strata ===')
L['cs']=pd.qcut(L.cand,4,labels=['vol Q1','vol Q2','vol Q3','vol Q4'],duplicates='drop')
for cs,sub in L.groupby('cs',observed=True):
    if len(sub)<8: continue
    sub=sub.copy()
    sub['g2']=pd.qcut(sub.gold,2,labels=['low gold','high gold'],duplicates='drop')
    t=sub.groupby('g2',observed=True).agg(n=('coicop','size'),gold=('gold','median'),
        cand=('cand','median'),acc=('acc_rate','median'),gaprate=('gap_rate','median'))
    rr,pp=spearmanr(sub.gold,sub.acc_rate)
    print(f'\n-- {cs} (n={len(sub)}, cand median {sub.cand.median():.0f}) spearman={rr:.3f} p={pp:.3f}')
    print(t.round(3).to_string())
