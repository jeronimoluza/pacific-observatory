# -*- coding: utf-8 -*-
import pandas as pd
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
P=pd.read_csv(BASE+'/label_pack_gapfill_20260909.csv')
for ct in ['fiji','samoa','tonga','papua_new_guinea','mongolia','japan']:
    s=P[P.country==ct]
    print(f'\n===== {ct}  n={len(s)} =====')
    print(s.sample(min(6,len(s)),random_state=5)[['product_name','current_pred','candidate_for','reason','score']].to_string(index=False)[:1500])
