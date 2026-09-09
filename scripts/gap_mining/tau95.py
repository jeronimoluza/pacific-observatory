import pandas as pd, numpy as np
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
c=pd.read_parquet(BASE+'/candidate_census.parquet')
# bands: b_lt90 <.073, b_90 .073-.1713, b_92 .1713-.5893, b_95 .5893-.9376, b_98 .9376-.9437, b_prod >=.9437
b=c.pivot_table(index=['country','proposed_leaf'],columns='band',values='n',aggfunc='sum',observed=True).fillna(0)
for col in ['b_lt90','b_90','b_92','b_95','b_98','b_prod']:
    if col not in b: b[col]=0
b['cand']=b[['b_lt90','b_90','b_92','b_95','b_98','b_prod']].sum(axis=1)
b['acc_old']=b[['b_98','b_prod']].sum(axis=1)              # tau 0.9437 (frozen) ~ prod+98 band
b['acc_95']=b[['b_95','b_98','b_prod']].sum(axis=1)        # tau 0.5893  SHIPPED
b['acc_92']=b[['b_92','b_95','b_98','b_prod']].sum(axis=1) # tau 0.1713
b=b.reset_index().rename(columns={'proposed_leaf':'coicop'})

M=pd.read_parquet(BASE+'/gap_triage_full.parquet')
M=M.drop(columns=[x for x in ['cand','cand_acc'] if x in M]).merge(
    b[['country','coicop','cand','acc_old','acc_95','acc_92']],on=['country','coicop'],how='left')
for col in ['cand','acc_old','acc_95','acc_92']: M[col]=M[col].fillna(0).astype(int)
gp=M[M.status=='gap']
print('gap cells:',len(gp))
for lab,accc in [('OLD tau 0.9437 (what my triage used)','acc_old'),
                 ('SHIPPED target_95 tau 0.5893','acc_95'),
                 ('target_92 tau 0.1713','acc_92')]:
    A=(gp.cand==0).sum(); B=((gp.cand>0)&(gp[accc]==0)).sum(); C=((gp.cand>0)&(gp[accc]>0)).sum()
    print(f'\n{lab}')
    print(f'  A no candidate        {A:5d} ({A/len(gp):5.1%})')
    print(f'  B classifier-blocked  {B:5d} ({B/len(gp):5.1%})   accepted rows: {int(gp.loc[(gp.cand>0)&(gp[accc]==0),accc].sum())}')
    print(f'  C accepted, unpublish {C:5d} ({C/len(gp):5.1%})   accepted rows: {int(gp.loc[gp[accc]>0,accc].sum()):,}')
print('\n=== cells that MOVE out of classifier-blocked by the shipped tau ===')
mv=gp[(gp.cand>0)&(gp.acc_old==0)&(gp.acc_95>0)]
print('cells unblocked:',len(mv),'| newly accepted rows:',int(mv.acc_95.sum()))
print(mv.groupby('country').size().sort_values(ascending=False).head(12).to_string())
