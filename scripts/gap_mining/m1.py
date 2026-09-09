import csv, re, collections
P='/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/inputs/EAP_Matrix(Sheet1).csv'
rows=list(csv.reader(open(P,encoding='utf-8-sig')))
hdr=rows[0]; countries=hdr[1:]
pat=re.compile(r'^((?:\d{2})(?:\.\d)*)(.*)$')
recs=[]
for r in rows[1:]:
    lab=r[0].strip()
    m=pat.match(lab)
    if not m: 
        print('NOMATCH',repr(lab)); continue
    code,name=m.group(1),m.group(2)
    depth=code.count('.')+1
    recs.append((code,name,depth,r[1:]))
print('rows parsed',len(recs))
bd=collections.Counter(d for _,_,d,_ in recs)
print('by depth',dict(sorted(bd.items())))
# fill status by depth
for d in sorted(bd):
    sub=[c for _,_,dd,c in recs if dd==d]
    n=v=dot=bl=0
    for cells in sub:
        for c in cells:
            c=c.strip(); n+=1
            if c=='·': dot+=1
            elif c=='': bl+=1
            else: v+=1
    print(f'depth {d}: rows={len(sub)} cells={n} value={v} ({v/n:.1%}) dot={dot} blank={bl}')
