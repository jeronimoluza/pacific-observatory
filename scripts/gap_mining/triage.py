import pandas as pd, numpy as np, csv, re, os

BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
CMAP={'Australia':'australia','Brunei Darussalam':'brunei_darussalam','Cambodia':'cambodia',
 'China':'china','Fiji':'fiji','French Polynesia':'french_polynesia','Guam':'guam',
 'Hong Kong SAR, China':'hong_kong_sar_china','Indonesia':'indonesia','Japan':'japan',
 'Lao PDR':'lao_pdr','Macao SAR, China':'macao_sar_china','Malaysia':'malaysia',
 'Mongolia':'mongolia','Myanmar':'myanmar','Nauru':'nauru','New Caledonia':'new_caledonia',
 'New Zealand':'new_zealand','Papua New Guinea':'papua_new_guinea','Philippines':'philippines',
 'Samoa':'samoa','Singapore':'singapore','Korea, Rep.':'south_korea','Taiwan, China':'taiwan_china',
 'Thailand':'thailand','Tonga':'tonga','Vanuatu':'vanuatu','Vietnam':'vietnam'}

# ---- 1. matrix -> long form of addressable cells
rows=list(csv.reader(open(os.path.join(BASE,'eap_matrix.csv'),encoding='utf-8-sig')))
cols=rows[0][1:]
pat=re.compile(r'^((?:\d{2})(?:\.\d)*)(.*)$')
recs=[]
for r in rows[1:]:
    m=pat.match(r[0].strip()); code,name=m.group(1),m.group(2)
    cells=[c.strip() for c in r[1:]]
    if not any(cells): continue
    for j,disp in enumerate(cols):
        if disp not in CMAP: continue
        st = 'gap' if cells[j]=='·' else ('filled' if cells[j] else 'na')
        if st=='na': continue
        recs.append(dict(coicop=code, leaf_name=name.strip(), disp=disp,
                         country=CMAP[disp], status=st))
M=pd.DataFrame(recs)
print('matrix cells:', len(M), ' gaps:', (M.status=='gap').sum())

# ---- 2. candidate census -> per (country, leaf)
c=pd.read_parquet(os.path.join(BASE,'candidate_census.parquet'))
c['n_rej']=c.n-c.n_acc
piv=(c.groupby(['country','proposed_leaf'])
       .agg(cand=('n','sum'), cand_acc=('n_acc','sum'), cand_fb=('n_fb','sum')).reset_index()
       .rename(columns={'proposed_leaf':'coicop'}))
bands=(c.pivot_table(index=['country','proposed_leaf'],columns='band',values='n',
                     aggfunc='sum',observed=True).fillna(0).astype(int).reset_index()
        .rename(columns={'proposed_leaf':'coicop'}))
piv=piv.merge(bands,on=['country','coicop'],how='left')

# ---- 3. gold counts
g=pd.read_parquet('/home/jeronimoluza/po/data/prices/enrich/gold/gold_labels.parquet',
                  columns=['country','code','verdict'])
g=g[g.code.notna()]
gc=g.groupby(['country','code']).size().rename('gold_ctry').reset_index().rename(columns={'code':'coicop'})
gg=g.groupby('code').size().rename('gold_global').reset_index().rename(columns={'code':'coicop'})

M=M.merge(piv,on=['country','coicop'],how='left').merge(gc,on=['country','coicop'],how='left').merge(gg,on='coicop',how='left')
for col in ['cand','cand_acc','cand_fb','gold_ctry','gold_global','b_lt90','b_90','b_92','b_95','b_98','b_prod']:
    if col in M: M[col]=M[col].fillna(0).astype(int)
    else: M[col]=0
M['cand_rej']=M.cand-M.cand_acc
M.to_parquet(os.path.join(BASE,'gap_triage.parquet'),index=False)

gp=M[M.status=='gap']
print('\n=== WHERE ARE THE 2,426 GAPS LOST? ===')
def bucket(r):
    if r.cand==0: return 'A_no_candidates'
    if r.cand_acc==0: return 'B_classifier_blocked'
    return 'C_accepted_but_unpublished'
gp=gp.assign(bucket=gp.apply(bucket,axis=1))
b=gp.groupby('bucket').agg(cells=('coicop','size'),cand=('cand','sum'),cand_acc=('cand_acc','sum'))
b['pct']=(b.cells/len(gp)*100).round(1)
print(b.to_string())
gp.to_parquet(os.path.join(BASE,'gap_triage_gaps.parquet'),index=False)

print('\n=== filled cells for contrast ===')
fl=M[M.status=='filled']
print('filled cells:',len(fl),' median cand:',int(fl.cand.median()),' median cand_acc:',int(fl.cand_acc.median()))
print('gap    cells:',len(gp),' median cand:',int(gp.cand.median()),' median cand_acc:',int(gp.cand_acc.median()))
