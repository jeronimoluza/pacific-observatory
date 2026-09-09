import pandas as pd, numpy as np
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
d=pd.read_parquet('/home/jeronimoluza/po/data/prices/build/global_prices_observations.parquet',
    columns=['coicop_code','country','observation_date','unit_value_local','qa_status'])
d['observation_date']=pd.to_datetime(d.observation_date,errors='coerce')
mx=d.observation_date.max()
print('obs',len(d),'max date',mx)
cut=mx-pd.Timedelta(days=60)
d['recent']=d.observation_date>=cut
d['trusted']=d.qa_status.eq('trusted')
o=(d.groupby(['country','coicop_code'])
     .agg(obs=('qa_status','size'),obs_trusted=('trusted','sum'),
          obs_recent=('recent','sum'),
          obs_rt=('qa_status',lambda s:0)).reset_index())
rt=(d[d.trusted&d.recent].groupby(['country','coicop_code']).size().rename('obs_recent_trusted').reset_index())
o=o.drop(columns=['obs_rt']).merge(rt,on=['country','coicop_code'],how='left')
o['obs_recent_trusted']=o.obs_recent_trusted.fillna(0).astype(int)
o=o.rename(columns={'coicop_code':'coicop'})
M=pd.read_parquet(BASE+'/gap_triage.parquet').merge(o,on=['country','coicop'],how='left')
for c in ['obs','obs_trusted','obs_recent','obs_recent_trusted']: M[c]=M[c].fillna(0).astype(int)
M.to_parquet(BASE+'/gap_triage_full.parquet',index=False)

gp=M[M.status=='gap']
print('\n=== BUCKET C (accepted-but-unpublished, 761 cells): where does it die? ===')
C=gp[gp.bucket=='C_accepted_but_unpublished'] if 'bucket' in gp else None
if C is None:
    def bk(r):
        if r.cand==0: return 'A_no_candidates'
        if r.cand_acc==0: return 'B_classifier_blocked'
        return 'C_accepted_but_unpublished'
    gp=gp.assign(bucket=gp.apply(bk,axis=1)); C=gp[gp.bucket=='C_accepted_but_unpublished']
print('cells',len(C))
for lab,q in [('no observation row at all',C.obs==0),
              ('obs exist, none trusted',(C.obs>0)&(C.obs_trusted==0)),
              ('trusted exist, none in 60d',(C.obs_trusted>0)&(C.obs_recent_trusted==0)),
              ('recent+trusted EXIST (matrix stale?)',C.obs_recent_trusted>0)]:
    print(f'  {lab:40s} {q.sum():4d}  ({q.sum()/len(C):5.1%})')
print('\n=== same view for ALL 2426 gaps ===')
for lab,q in [('no observation row at all',gp.obs==0),
              ('obs exist, none trusted',(gp.obs>0)&(gp.obs_trusted==0)),
              ('trusted exist, none in 60d',(gp.obs_trusted>0)&(gp.obs_recent_trusted==0)),
              ('recent+trusted EXIST',gp.obs_recent_trusted>0)]:
    print(f'  {lab:40s} {q.sum():5d}  ({q.sum()/len(gp):5.1%})')
print('\n=== sanity: filled cells ===')
fl=M[M.status=='filled']
print(f'  filled with recent+trusted obs: {(fl.obs_recent_trusted>0).sum()} / {len(fl)}')
