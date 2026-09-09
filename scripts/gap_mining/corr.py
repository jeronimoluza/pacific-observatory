import pandas as pd, numpy as np
from scipy.stats import spearmanr
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
M=pd.read_parquet(BASE+'/gap_triage.parquet')
L=(M.groupby(['coicop','leaf_name'])
     .agg(cells=('status','size'),
          gaps=('status',lambda s:(s=='gap').sum()),
          gold=('gold_global','max'),
          cand=('cand','sum'), cand_acc=('cand_acc','sum')).reset_index())
L['gap_rate']=L.gaps/L.cells
r,p=spearmanr(L.gold,L.gap_rate)
print(f'Spearman(gold_global, gap_rate) over {len(L)} leaves = {r:.3f}  p={p:.2e}')
r2,p2=spearmanr(L.cand,L.gap_rate)
print(f'Spearman(candidates,  gap_rate)                      = {r2:.3f}  p={p2:.2e}')
print()
print('=== gap rate by gold-label decile ===')
L['dec']=pd.qcut(L.gold,10,labels=False,duplicates='drop')
t=L.groupby('dec').agg(leaves=('coicop','size'),gold_med=('gold','median'),
                       gap_rate=('gap_rate','mean'),cand_med=('cand','median'))
t['gap_rate']=(t.gap_rate*100).round(1)
print(t.to_string())
print()
print('=== the 16 fully-covered leaves vs the 40 worst ===')
best=L.nsmallest(16,'gap_rate'); worst=L.nlargest(40,'gap_rate')
print(f'fully covered : median gold={best.gold.median():.0f}  median cand={best.cand.median():.0f}')
print(f'worst 40      : median gold={worst.gold.median():.0f}  median cand={worst.cand.median():.0f}')
L.sort_values(['gap_rate','gold'],ascending=[False,True]).to_csv(BASE+'/leaf_gap_vs_gold.csv',index=False)
print('\nwrote leaf_gap_vs_gold.csv')
