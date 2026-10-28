"""Load fixed corpus records and official documents produced by crawl_official.py."""
from pathlib import Path
import json, hashlib
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]
URL='https://modelscope.cn/datasets/BAAI/IndustryCorpus2'
SELECT={
 '黄山':[22371,26300,39623,55788,112521],
 '九寨沟':[21748,38314,45961,70708,97333],
 '张家界':[12043,37937,79780,119817,200430],
}
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
def base(doc_id,scenic,kind,source,url,original,**kw):
 return dict(doc_id=doc_id,scenic=scenic,text_type=kind,source_name=source,source_url=url,
  original_url=url if kind=='官方路线' else '',original_text=original,acquired_date='2026-10-28',**kw)
rows=[];offset=0;manifest=[]
for p in sorted((ROOT/'data/source').glob('*.parquet')):
 pf=pq.ParquetFile(p); manifest.append(dict(file=p.name,rows=pf.metadata.num_rows,bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),dataset_path='tourism_geography/chinese/'+('high/' if '00130' in p.name else 'middle/')+p.name))
 targets={i:(s,k+1) for s,idx in SELECT.items() for k,i in enumerate(idx)}
 local=0
 for batch in pf.iter_batches(batch_size=4096):
  for r in batch.to_pylist():
   g=offset+local
   if g in targets:
    scenic,k=targets[g];prefix={'黄山':'HS','九寨沟':'JZG','张家界':'ZJJ'}[scenic]
    rows.append(base(f'{prefix}-T{k:02}',scenic,'游客游记','BAAI/IndustryCorpus2',URL,r['text'],
      source_record_id=str(r['_id']),source_file=p.name,source_row_index=local,
      title=r['text'].splitlines()[0][:60],quality_score=r['quality_score'],
      provenance_status='语料记录可追溯；原发布者及网页未核验',classification_basis='正文含本人/同行者游览经历与具体景点、行程；内容判定为游记，不代表原平台身份认证',
      scope_note='张家界以武陵源为核心，保留游记中的天门山、黄龙洞及凤凰古城等外围行程，后续抽取须按地点过滤' if scenic=='张家界' else '原文历史价格、开放状态及主观描述均非现行事实核验结果'))
   local+=1
 offset+=local
assert len(rows)==15
# Official documents are produced by the independent crawler.
official_path = ROOT / 'data/raw/official_routes.jsonl'
if not official_path.exists():
 raise FileNotFoundError('Run python src/crawl_official.py first (or --offline for saved snapshots)')
official = [json.loads(line) for line in official_path.read_text(encoding='utf-8').splitlines()]
assert {r['doc_id'] for r in official} == {'HS-O01', 'JZG-O01', 'ZJJ-O01'}
rows.extend(official)
rows.sort(key=lambda r:r['doc_id'])
(ROOT/'data/raw/selected_raw.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
dump(ROOT/'data/source/manifest.json',dict(dataset=URL,revision_observed='228165f30a56b40ca8aea38d88ba58046a2428ea',acquired_date='2026-10-28',files=manifest,total_scanned=offset,selected=SELECT,selection_note='探索性目的抽样，非随机抽样；按正文主题与行程信息复核筛选；原网页URL缺失不编造'))
print('Prepared',len(rows),'records from',offset,'corpus rows')
