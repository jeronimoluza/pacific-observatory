import csv, re, collections
P='/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/inputs/EAP_Matrix(Sheet1).csv'
rows=list(csv.reader(open(P,encoding='utf-8-sig')))
countries=rows[0][1:]
pat=re.compile(r'^((?:\d{2})(?:\.\d)*)(.*)$')
recs=[]
for r in rows[1:]:
    m=pat.match(r[0].strip())
    code,name=m.group(1),m.group(2)
    recs.append((code,name,code.count('.')+1,[c.strip() for c in r[1:]]))
# addressable = any cell is value or dot
addr=[(c,n,d,cells) for c,n,d,cells in recs if any(x for x in cells)]
print('addressable leaf rows:',len(addr))
print()
print('=== PER-COUNTRY (sorted by gap rate) ===')
per=[]
for i,ct in enumerate(countries):
    v=sum(1 for _,_,_,cells in addr if cells[i] not in ('','·'))
    g=sum(1 for _,_,_,cells in addr if cells[i]=='·')
    per.append((ct,v,g,g/(v+g) if v+g else 0))
for ct,v,g,r in sorted(per,key=lambda x:-x[3]):
    print(f'{ct:28s} filled={v:4d} gap={g:4d} gaprate={r:6.1%}')
print()
print('=== PER-DIVISION rollup ===')
div=collections.defaultdict(lambda:[0,0])
for c,n,d,cells in addr:
    k=c[:4] if len(c)>=4 else c[:2]
    for x in cells:
        if x=='·': div[k][1]+=1
        elif x: div[k][0]+=1
for k in sorted(div):
    v,g=div[k]; print(f'{k:6s} filled={v:5d} gap={g:5d} gaprate={g/(v+g):6.1%}')
