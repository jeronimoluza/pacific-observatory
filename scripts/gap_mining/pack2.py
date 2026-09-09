# -*- coding: utf-8 -*-
"""Assemble the gap-fill label pack.
Sources: (1) uncertainty - model proposed the exact target leaf but rejected it;
         (2) sibling     - model landed in the target leaf's PARENT family, wrong/rejected leaf.
Lexical mining is deliberately excluded: CJK substring precision was too low (see spot.py).
Stratified so no country or family dominates."""
import pandas as pd, numpy as np, datetime
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
M=pd.read_parquet(BASE+'/gap_triage_full.parquet')
tgt=pd.read_csv(BASE+'/target_leaves.csv')
names=M[['coicop','leaf_name']].drop_duplicates().set_index('coicop').leaf_name.to_dict()
def par(c): return '.'.join(c.split('.')[:-1])

gaps=M[(M.status=='gap')&(M.coicop.isin(set(tgt.coicop)))].copy()
gaps['fam']=gaps.coicop.map(par)
fammap=(gaps.groupby(['country','fam']).coicop.apply(lambda s:','.join(sorted(set(s)))).rename('candidate_for').reset_index())
famname=(gaps.groupby(['country','fam']).coicop
           .apply(lambda s:' | '.join(names.get(x,'') for x in sorted(set(s)))).rename('candidate_for_names').reset_index())

# --- source 1
U=pd.read_parquet(BASE+'/candidates_raw.parquet')
U=U[~U.accepted].copy()
U['fam']=U.coicop.map(par); U['reason']='uncertainty'
U=U.rename(columns={'coicop':'current_pred'})[['name','country','fam','current_pred','score','script','reason']]

# --- source 2
S=pd.read_parquet(BASE+'/sibling_candidates.parquet')
S=S[~S.accepted].copy()
S=S.rename(columns={'parent_pred':'fam','proposed_leaf':'current_pred'})
S['reason']='sibling'
S=S[['name','country','fam','current_pred','score','script','reason']]

C=pd.concat([U,S],ignore_index=True)
C['src_rank']=C.reason.map({'uncertainty':0,'sibling':1})
C=C.sort_values('src_rank').drop_duplicates(subset=['name','country','fam'])   # uncertainty wins ties
C=C.merge(fammap,on=['country','fam'],how='inner').merge(famname,on=['country','fam'],how='left')
print('pooled candidates:',len(C),'| countries',C.country.nunique(),'| families',C.fam.nunique())

# --- stratify: equal-ish per country, then per family within country, prefer boundary scores
PER_COUNTRY=450; PER_FAM=30
rng=np.random.default_rng(11)
def pick(g,k):
    if len(g)<=k: return g
    # uncertainty rows first, then the rows closest to the decision boundary
    return (g.assign(_d=(g.score-0.5).abs())
             .sort_values(['src_rank','_d']).head(k).drop(columns='_d'))
step1=C.groupby(['country','fam'],group_keys=False).apply(lambda g:pick(g,PER_FAM))
P=step1.groupby('country',group_keys=False).apply(lambda g:pick(g,PER_COUNTRY))
P=P.rename(columns={'name':'product_name','fam':'parent_family'})
P=P[['country','product_name','parent_family','candidate_for','candidate_for_names',
     'current_pred','score','script','reason']].sort_values(['country','parent_family','score'])
stamp=datetime.date.today().strftime('%Y%m%d')
out=f'{BASE}/label_pack_gapfill_{stamp}.csv'
P.to_csv(out,index=False)
print('\nLABEL PACK ->',out)
print('rows',len(P),'| countries',P.country.nunique(),'| families',P.parent_family.nunique())
print('gap cells addressed:',gaps[gaps.set_index(["country","fam"]).index.isin(P.set_index(["country","parent_family"]).index)].shape[0],'of',len(gaps))
print('\nby reason:'); print(P.groupby('reason').size().to_string())
print('\nby script:'); print(P.groupby('script').size().sort_values(ascending=False).to_string())
print('\nrows per country:'); print(P.groupby('country').size().sort_values(ascending=False).to_string())
