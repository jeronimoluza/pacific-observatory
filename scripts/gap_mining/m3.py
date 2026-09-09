import csv, re
P='/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/inputs/EAP_Matrix(Sheet1).csv'
rows=list(csv.reader(open(P,encoding='utf-8-sig')))
countries=rows[0][1:]
ci=[i for i,c in enumerate(countries) if c!='East Asia & Pacific']  # 28 real countries
pat=re.compile(r'^((?:\d{2})(?:\.\d)*)(.*)$')
addr=[]
for r in rows[1:]:
    m=pat.match(r[0].strip()); cells=[c.strip() for c in r[1:]]
    if any(cells): addr.append((m.group(1),m.group(2),cells))
print('leaves',len(addr),'countries',len(ci))
rank=[]
for code,name,cells in addr:
    g=sum(1 for i in ci if cells[i]=='·')
    rank.append((g,code,name))
rank.sort(reverse=True)
tot=sum(g for g,_,_ in rank)
print(f'TOTAL GAP CELLS (28 countries): {tot}\n')
print('=== 40 WORST LEAVES (missing in most countries) ===')
for g,code,name in rank[:40]:
    print(f'{g:3d}/28  {code:10s} {name[:62]}')
print('\n=== FULLY COVERED LEAVES (0 gaps) ===', sum(1 for g,_,_ in rank if g==0))
print('=== LEAVES MISSING EVERYWHERE (28/28) ===', sum(1 for g,_,_ in rank if g==28))
