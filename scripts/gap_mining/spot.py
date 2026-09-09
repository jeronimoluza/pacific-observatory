# -*- coding: utf-8 -*-
import pandas as pd
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
L=pd.read_parquet(BASE+'/lexical_candidates.parquet')
X=L[~L.already_right]
for leaf in ['01.1.6.5.5','01.1.1.1.1','01.1.3.1.4','01.1.7.5.5','01.1.7.4.6','01.1.1.1.5']:
    s=X[X.target_leaf==leaf]
    print(f'\n=== {leaf}  n={len(s)} ===')
    print(s.sample(min(8,len(s)),random_state=3)[['country','name','proposed_leaf','score']].to_string(index=False)[:1400])
