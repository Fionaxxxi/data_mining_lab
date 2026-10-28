from pathlib import Path
import json,re,collections
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[3]
p=ROOT/'data/source/rank_00130.parquet'
t=pq.read_table(p)
print(t.schema)
print('ROWS',len(t))
names=['故宫','颐和园','黄山','九寨沟','张家界','西湖','泰山','华山','峨眉山','武夷山','鼓浪屿','长隆','迪士尼','兵马俑','天坛','普陀山','庐山','乌镇']
rows=t.to_pylist(); out=[]; counts=collections.Counter()
for i,r in enumerate(rows):
 s=r.get('text','') or ''
 hits=[n for n in names if n in s]
 if hits and re.search('路线|游记|攻略|游览|一日游',s):
  counts.update(hits)
  out.append(dict(row_index=i,scenic_hits=hits,**r))
print(counts)
(ROOT/'data/raw/candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in out),encoding='utf-8')
for n in names:
 ss=[r for r in out if n in r['scenic_hits']]
 print('\nSCENIC',n,len(ss))
 for r in ss[:12]:print(r['row_index'],str(r.get('_id')),len(r['text']),r['text'][:200].replace('\n',' / '))
