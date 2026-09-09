# -*- coding: utf-8 -*-
import pandas as pd, numpy as np, glob, os, re, time
BASE='/home/jeronimoluza/po-worktrees/gap-mining/outputs'
SRC='/home/jeronimoluza/po/data/prices/enrich/_hierlex_pred/hierlex_select_v1_20260908'

# leaf -> (latin word-boundary terms, non-latin substring terms). Risky 1-char Hangul/Viet dropped.
PACK = {
 '01.1.7.5.5': (['taro','satoimo','dalo','gabi','keladi','colocasia','eddoe'], ['里芋','タロイモ','토란','芋頭','khoai môn']),
 '01.1.7.5.4': (['yam','ube','uhi'], ['山芋','長芋','ヤムイモ','khoai mỡ']),
 '01.1.7.5.7': (['plantain','cooking banana','saba banana','vudi','pulaka'], ['調理用バナナ','chuối sứ','chuối xanh']),
 '01.1.7.1.7': (['cassava leaf','cassava leaves','daun singkong'], ['木薯叶','lá sắn']),
 '01.1.7.5.6': (['cassava','manioc','singkong','ubi kayu','kamoteng kahoy'], ['木薯','キャッサバ','khoai mì']),
 '01.1.6.1.7': (['pineapple','nanas','pinya'], ['パイナップル','菠萝','鳳梨','파인애플','dứa']),
 '01.1.6.5.5': (['persimmon','kesemek'], ['柿子','かき','감','hồng giòn']),
 '01.1.6.1.4': (['fig','figs','buah tin'], ['いちじく','イチジク','无花果','無花果','무화과']),
 '01.1.6.3.3': (['apricot','aprikot'], ['あんず','アプリコット','杏子','살구']),
 '01.1.6.3.4': (['cherry','cherries','ceri'], ['さくらんぼ','チェリー','樱桃','櫻桃','체리','anh đào']),
 '01.1.6.8.3': (['chestnut','chestnuts','kastanye'], ['栗','くり','板栗','hạt dẻ']),
 '01.1.6.8.5': (['pistachio','pistachios'], ['ピスタチオ','开心果','開心果','피스타치오']),
 '01.1.6.8.8': (['groundnut','groundnuts','raw peanut','kacang tanah'], ['落花生','花生','땅콩','đậu phộng']),
 '01.1.1.1.6': (['maize','corn kernel','dried corn','jagung'], ['とうもろこし','トウモロコシ','玉米','옥수수']),
 '01.1.1.1.5': (['millet'], ['小米','雑穀','기장']),
 '01.1.1.1.3': (['sorghum','jowar'], ['高粱','수수','cao lương']),
 '01.1.1.1.1': (['wheat grain','wheat berries','gandum'], ['小麦','lúa mì']),
 '01.1.7.6.3': (['chickpea','chickpeas','garbanzo'], ['ひよこ豆','鹰嘴豆','鷹嘴豆','병아리콩','đậu gà']),
 '01.1.7.6.5': (['dried pea','dried peas','split pea'], ['干豌豆','đậu Hà Lan khô']),
 '01.1.7.6.6': (['cow pea','cowpea','cowpeas','black eyed pea'], ['ささげ','豇豆','đậu trắng']),
 '01.1.7.6.7': (['pigeon pea','pigeon peas','toor dal'], ['木豆','đậu triều']),
 '01.1.7.3.5': (['edamame','green soybean','soya bean fresh'], ['枝豆','えだまめ','毛豆','풋콩']),
 '01.1.3.1.5': (['tuna','skipjack','bonito','yellowfin','katsuo','tongkol','cakalang'], ['まぐろ','マグロ','かつお','カツオ','金枪鱼','鮪魚','참치','cá ngừ']),
 '01.1.3.1.3': (['flounder','halibut','plaice','turbot','ikan sebelah'], ['ひらめ','ヒラメ','かれい','カレイ','比目鱼','넙치','가자미','cá bơn']),
 '01.1.3.1.4': (['cod fillet','cod loin','haddock','pollock','hake'], ['たら','タラ','鱈','鳕鱼','대구','cá tuyết']),
 '01.1.7.4.6': (['seaweed','nori','wakame','kombu','sea grapes','limu'], ['海苔','わかめ','ワカメ','昆布','海藻','미역','다시마','rong biển']),
 '02.3.0.2':   (['cigar','cigars','cerutu'], ['葉巻','雪茄','xì gà']),
 '01.1.5.1.5': (['groundnut oil','peanut oil','minyak kacang'], ['落花生油','花生油','땅콩기름','dầu đậu phộng']),
 '01.1.5.9.1': (['lard','minyak babi'], ['ラード','猪油','豬油','라드','mỡ lợn','mỡ heo']),
 '01.1.4.1.3': (['goat milk','goats milk','sheep milk','susu kambing'], ['ヤギミルク','山羊乳','羊乳','염소우유','sữa dê']),
}
gaps=pd.read_parquet(BASE+'/gap_triage_full.parquet').query("status=='gap'")
gset={}
for co,ct in zip(gaps.coicop,gaps.country): gset.setdefault(co,set()).add(ct)
PACK={k:v for k,v in PACK.items() if k in gset}
allc=set().union(*[gset[k] for k in PACK])
print('leaves',len(PACK),'countries',len(allc),flush=True)

def lat_re(ts): return re.compile(r'(?<![A-Za-z])(?:'+'|'.join(re.escape(t) for t in ts)+r')(?![A-Za-z])',re.I)
per={k:(lat_re(v[0]) if v[0] else None, v[1]) for k,v in PACK.items()}
ALLT=[t for v in PACK.values() for t in v[0]]
ALLN=[t for v in PACK.values() for t in v[1]]
MASTER=re.compile('(?:'+lat_re(ALLT).pattern+')|(?:'+'|'.join(re.escape(t) for t in ALLN)+')',re.I)

files=sorted(glob.glob(os.path.join(SRC,'pred_*.parquet')))
hits=[]; t0=time.time()
for i,f in enumerate(files):
    d=pd.read_parquet(f,columns=['name','country','proposed_leaf','calibrated_correctness_score','accepted','script'])
    d=d[d.country.isin(allc)]
    if not len(d): continue
    s=d.name.fillna('')
    d=d[s.str.contains(MASTER,na=False)]          # ONE pass
    if not len(d): continue
    s=d.name.fillna('')
    for leaf,(lr,nt) in per.items():
        cs=gset[leaf]
        m=d.country.isin(cs)
        if not m.any(): continue
        mm=pd.Series(False,index=d.index)
        if lr is not None: mm|=s.str.contains(lr,na=False)
        for t in nt: mm|=s.str.contains(t,regex=False,na=False)
        mm&=m
        if mm.any():
            h=d[mm].copy(); h['target_leaf']=leaf; hits.append(h)
    if (i+1)%64==0: print(f'  {i+1}/{len(files)} hits={sum(len(h) for h in hits)} {time.time()-t0:.0f}s',flush=True)

H=pd.concat(hits,ignore_index=True).rename(columns={'calibrated_correctness_score':'score'})
H['already_right']=H.proposed_leaf.eq(H.target_leaf)&H.accepted
H.to_parquet(BASE+'/lexical_candidates.parquet',index=False)
print('\nlexical hits inside GAP cells:',len(H))
print('  already correct+accepted:',int(H.already_right.sum()))
print('  MISFILED/REJECTED -> label candidates:',int((~H.already_right).sum()))
X=H[~H.already_right]
print('\nby target leaf:'); print(X.groupby('target_leaf').size().sort_values(ascending=False).head(20).to_string())
print('\nby country:');     print(X.groupby('country').size().sort_values(ascending=False).head(25).to_string())
