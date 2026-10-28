"""Load fixed corpus records and manually selected official passages; no crawler."""
from pathlib import Path
import json, hashlib,re
from bs4 import BeautifulSoup
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
# Official Huangshan: original HTML body paragraphs, Q20 only.
s=BeautifulSoup((ROOT/'data/source/official_huangshan.html').read_bytes(),'html.parser')
script=s.find('script',string=lambda x:x and 'var data=' in x)
payload=json.loads(re.search(r'var data=(\[.*?\]);',script.string,re.S).group(1))
body=BeautifulSoup(payload[0]['data']['content'],'html.parser')
ps=body.find_all('p'); start=next(i for i,p in enumerate(ps) if '20.清明假期' in p.get_text());end=next(i for i,p in enumerate(ps[start+1:],start+1) if '21.黄山' in p.get_text())
raw='\n'.join(str(p) for p in ps[start:end])
rows.append(base('HS-O01','黄山','官方路线','黄山旅游官方平台','https://wap.huangshan.com.cn/detail/strategy/fjqlyzx',raw,
 title='黄山风景区清明假期常见旅游咨询 第20问路线节选',source_record_id='fjqlyzx-Q20',source_file='official_huangshan.html',source_row_index=None,quality_score=None,provenance_status='景区官方平台；已保存HTML快照',classification_basis='官方旅游平台发布的路线推荐；一份指南可含多条候选线路',scope_note='历史清明咨询路线，仅作文本挖掘材料，非2026年开放与票务承诺'))
# Jiuzhaigou: capture only the one-day-tour passage, from the live saved page.
s=BeautifulSoup((ROOT/'data/source/official_jiuzhai.html').read_bytes(),'html.parser')
h=s.find(string=lambda x:x and x.strip()=='一日精华游')
anchor=h.find_parent('div',class_='g-content')
raw=str(anchor)
assert '沟口乘车' in raw and '13:30' in raw
rows.append(base('JZG-O01','九寨沟','官方路线','九寨沟风景名胜区管理局','https://www.jiuzhai.com/intelligent-service/way-of-play',raw,
 title='游玩方式 一日精华游节选',source_record_id='way-of-play-one-day',source_file='official_jiuzhai.html',source_row_index=None,quality_score=None,provenance_status='景区官方网站；已保存HTML快照',classification_basis='景区管理局官方网站的一日精华游推荐',scope_note='保留原文时间，包括末段17:00起点早于前段终点的疑似时间重叠，不擅自修订'))
raw=(ROOT/'data/raw/official_zhangjiajie_excerpt.txt').read_text(encoding='utf-8')
rows.append(base('ZJJ-O01','张家界','官方路线','湖南省文化和旅游厅','https://whhlyt.hunan.gov.cn/whhlyt/wldhlylx/202208/t20220816_27584140.html',raw,
 title='直达武陵源 乐享张家界 武陵源自驾一日游节选',source_record_id='t20220816_27584140-one-day',source_file='official_zhangjiajie_excerpt.txt',source_row_index=None,quality_score=None,provenance_status='官方页面检索阅读核验；人工摘录，未取得HTML快照',classification_basis='省文旅厅官网发布，文末署名武陵源区委旅游工作委员会办公室',scope_note='网页发布日期2022-08-16，文末署名日期2021-09-18；日期均保留在来源说明中，不视为2026年路线更新'))
rows.sort(key=lambda r:r['doc_id'])
(ROOT/'data/raw/selected_raw.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
dump(ROOT/'data/source/manifest.json',dict(dataset=URL,revision_observed='228165f30a56b40ca8aea38d88ba58046a2428ea',acquired_date='2026-10-28',files=manifest,total_scanned=offset,selected=SELECT,selection_note='探索性目的抽样，非随机抽样；按正文主题与行程信息复核筛选；原网页URL缺失不编造'))
print('Prepared',len(rows),'records from',offset,'corpus rows')
