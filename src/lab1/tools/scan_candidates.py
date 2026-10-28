from pathlib import Path
import json,re,collections
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[3]
names=['故宫','颐和园','黄山','九寨沟','张家界','西湖','泰山','华山','峨眉山','武夷山','鼓浪屿','长隆','迪士尼','兵马俑','天坛','普陀山','庐山','乌镇']
out=[]; total=0; counts=collections.Counter()
for p in sorted((ROOT/'data/source').glob('*.parquet')):
 t=pq.ParquetFile(p)
 print(p.name,t.metadata.num_rows,flush=True)
 for batch in t.iter_batches(batch_size=2048):
  for r in batch.to_pylist():
   idx=total; total+=1;s=r.get('text') or ''
   hits=[n for n in names if n in s[:250] and not (n=='华山' and '九华山' in s[:250]) and not (n=='黄山' and '小黄山' in s[:250]) and not (n=='西湖' and '瘦西湖' in s[:250])]
   if hits and re.search('路线|游记|攻略|游览|一日游|我们|我和|游玩',s):
    counts.update(hits)
    out.append(dict(source_file=p.name,row_index=idx-(total-t.metadata.num_rows) if False else idx,scenic_hits=hits,**r))
(ROOT/'data/raw/all_candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in out),encoding='utf-8')
print('TOTAL',total,'CANDIDATES',len(out),counts)
for n in names:
 ss=[r for r in out if n in r['scenic_hits']]
 ranked=sorted(ss,key=lambda r: -(len(re.findall('路线|攻略|游记|我们|我和|上午|下午|建议',r['text']))+15*bool(re.search('游记|攻略|路线',r['text'][:100]))))
 print('\n###',n)
 for r in ranked[:12]:print(r['source_file'],r['row_index'],r['_id'],len(r['text']),r['text'][:85].replace('\n',' / '))
