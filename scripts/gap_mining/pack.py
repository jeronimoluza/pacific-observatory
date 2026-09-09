# -*- coding: utf-8 -*-
import pandas as pd, numpy as np, os, datetime
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
M=pd.read_parquet(BASE+'/gap_triage_full.parquet')
names=M[['coicop','leaf_name']].drop_duplicates()

# --- source 1: uncertainty sampling (model proposed the target leaf but rejected it)
U=pd.read_parquet(BASE+'/candidates_raw.parquet')
U=U[~U.accepted].copy()
U['target_leaf']=U.coicop; U['reason']='uncertainty'
U['current_pred']=U.coicop
U=U[['name','country','target_leaf','current_pred','score','script','reason']]

# --- source 2: lexical sweep (term match inside a gap cell, model got it wrong/rejected)
L=pd.read_parquet(BASE+'/lexical_candidates.parquet')
L=L[~L.already_right].copy()
L['reason']=np.where(L.proposed_leaf.eq(L.target_leaf),'lexical_rejected','lexical_misfiled')
L=L.rename(columns={'proposed_leaf':'current_pred'})[['name','country','target_leaf','current_pred','score','script','reason']]

C=pd.concat([U,L],ignore_index=True).drop_duplicates(subset=['name','country','target_leaf'])
C=C.merge(names.rename(columns={'coicop':'target_leaf'}),on='target_leaf',how='left')

# --- stratified sampling: cap per (leaf,country) so no cell dominates; language balance via script
CAP=40
rng=np.random.default_rng(7)
def take(g):
    if len(g)<=CAP: return g
    # prefer the most informative: score nearest the decision boundary, spread across scripts
    g=g.assign(_d=(g.score-0.5).abs())
    return g.nsmallest(CAP,'_d').drop(columns='_d')
P=C.groupby(['target_leaf','country'],group_keys=False).apply(take)

# --- priority: gap cells the leaf would unlock x how starved it is
L2=(M.groupby('coicop').agg(gaps=('status',lambda s:(s=='gap').sum()),gold=('gold_global','max')).reset_index()
      .rename(columns={'coicop':'target_leaf'}))
P=P.merge(L2,on='target_leaf',how='left')
P['priority']=(P.gaps/P.gaps.max())*0.6+(1-P.gold/P.gold.max())*0.4
P=P.sort_values(['priority','target_leaf','country'],ascending=[False,True,True])
P=P[['target_leaf','leaf_name','country','name','current_pred','score','script','reason','gaps','gold','priority']]
P=P.rename(columns={'name':'product_name','gaps':'gap_cells_leaf','gold':'gold_labels_leaf'})
stamp=datetime.date.today().strftime('%Y%m%d')
out=f'{BASE}/label_pack_gapfill_{stamp}.csv'
P.to_csv(out,index=False)
print('LABEL PACK ->',out)
print('rows',len(P),' leaves',P.target_leaf.nunique(),' countries',P.country.nunique())
print('\nby reason:'); print(P.groupby('reason').size().to_string())
print('\nby script:'); print(P.groupby('script').size().sort_values(ascending=False).head(8).to_string())
print('\ntop 12 leaves:'); print(P.groupby(['target_leaf','leaf_name']).size().sort_values(ascending=False).head(12).to_string())
print('\ncountry spread (all):'); print(P.groupby('country').size().sort_values(ascending=False).to_string())
print('\n--- sample rows ---')
print(P.head(18)[['target_leaf','country','product_name','current_pred','reason']].to_string(index=False))
