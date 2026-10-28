"""Offline reproducible batch cleaning and quality audit. Run after prepare_data.py."""
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher
import csv,json,re,html,unicodedata,hashlib,sys,platform
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs'; OUT.mkdir(exist_ok=True)
META=re.compile(r'^\s*(?:\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}|来源\s*[:：]|原标题\s*[:：]|\[责任编辑[:：]|作者系|指导老师[:：]|地址[:：].*电话[:：])')
TAILS=['[责任编辑:','[责任编辑：','本篇游记共含','特别声明:以上文章','特别声明：以上文章',
 '特色:全程使用2+1豪华陆地头等舱保姆车出行',
 '若有需要转载或使用游记以及其中的图文,须在征得本人同意的情况下',
 '关于作者:85后青年,自助行,户外及登山爱好者']
def sub(s,pat,repl,name,events,flags=0):
 s,n=re.subn(pat,repl,s,flags=flags)
 if n:events[name]+=n
 return s
def clean_text(raw):
 e=Counter();s=raw
 if re.search(r'</?[A-Za-z][^>]*>',s):
  soup=BeautifulSoup(s,'html.parser')
  for node in soup(['script','style','noscript']):node.decompose()
  for br in soup.find_all('br'):br.replace_with('\n')
  for node in soup.find_all(['p','div','h1','h2','h3']):node.append('\n')
  for node in soup.find_all('font'):node.append('\n')
  s=soup.get_text('',strip=False); e['html_removed']=1
 v=html.unescape(s)
 if v!=s:e['html_entities_decoded']=1
 s=v
 s=sub(s,r'\r\n?|\u2028|\u2029','\n','line_endings_normalized',e)
 s=sub(s,r'[\u200b-\u200f\ufeff\x00-\x08\x0b\x0c\x0e-\x1f\x7f]','','control_chars_removed',e)
 # Target only fullwidth ASCII; preserve other symbols, circled numerals and arrows.
 v=''.join(chr(ord(c)-0xFEE0) if 0xFF01<=ord(c)<=0xFF5E else c for c in s)
 if v!=s:e['fullwidth_ascii_normalized']=1
 s=v.replace('\u3000',' ').replace('\xa0',' ')
 for marker in TAILS:
  if marker in s:
   s=s[:s.index(marker)];e['web_tail_removed']+=1
 s=sub(s,r'图片发自简书app','','image_placeholder_removed',e)
 s=sub(s,r'\(图文:@[^\n)]*\)\s*$','','author_credit_removed',e)
 s=sub(s,r'https?://[^\s<>\"\u4e00-\u9fff]+','','inline_url_removed',e)
 lines=[]
 for line in s.split('\n'):
  if META.match(line):e['metadata_line_removed']+=1;continue
  line=re.sub(r'[\t \f\v]+',' ',line).strip()
  if line:lines.append(line)
 s='\n'.join(lines)
 if s!=v:e['whitespace_or_noise_normalized']=1
 return s,dict(e)
def write_csv(path,rows):
 if not rows:return
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 raw=[json.loads(x) for x in (ROOT/'data/raw/selected_raw.jsonl').read_text(encoding='utf-8').splitlines()]
 accepted=[];reject=[];seen={};audit=[];rule_count=Counter()
 for r in raw:
  text,e=clean_text(r['original_text']);rule_count.update(e)
  reason=''
  if not text:reason='empty_clean_text'
  elif r['scenic'] not in ['黄山','九寨沟','张家界']:reason='invalid_scenic'
  elif r['text_type'] not in ['官方路线','游客游记']:reason='invalid_type'
  fingerprint=hashlib.sha256(text.encode('utf-8')).hexdigest()
  if fingerprint in seen:reason='duplicate_of:'+seen[fingerprint]
  if reason:reject.append(dict(doc_id=r['doc_id'],reason=reason));continue
  seen[fingerprint]=r['doc_id']
  r=dict(r,clean_text=text,original_chars=len(r['original_text']),clean_chars=len(text),content_sha256=fingerprint)
  accepted.append(r)
  notes=[]
  if '\ufffd' in text:notes.append('replacement_character_needs_review')
  if re.search('不雅鉴赏|人平易近|年夜夫',text):notes.append('suspected_rewrite_noise')
  if re.search('逃掉|封山|钻过去|喂食|扔过去',text):notes.append('historical_or_inappropriate_behaviour_not_recommendation')
  audit.append(dict(doc_id=r['doc_id'],scenic=r['scenic'],text_type=r['text_type'],original_chars=r['original_chars'],clean_chars=r['clean_chars'],changed=text!=r['original_text'],rules=json.dumps(e,ensure_ascii=False),review_notes=';'.join(notes)))
 write_csv(OUT/'cleaned_data.csv',accepted)
 (OUT/'cleaned_data.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in accepted),encoding='utf-8')
 write_csv(OUT/'cleaning_audit.csv',audit)
 write_csv(OUT/'source_index.csv',[{k:r[k] for k in ['doc_id','scenic','text_type','title','source_name','source_url','original_url','source_file','source_record_id','source_row_index','provenance_status','scope_note']} for r in accepted])
 counts=[]
 for s in ['黄山','九寨沟','张家界']:
  counts.append(dict(scenic=s,official_documents=sum(r['scenic']==s and r['text_type']=='官方路线' for r in accepted),travel_documents=sum(r['scenic']==s and r['text_type']=='游客游记' for r in accepted)))
 write_csv(OUT/'scenic_counts.csv',counts)
 near=[]
 for i,a in enumerate(accepted):
  for b in accepted[i+1:]:
   if a['scenic']==b['scenic'] and a['text_type']==b['text_type']:
    ratio=SequenceMatcher(None,a['clean_text'],b['clean_text'],autojunk=False).ratio()
    if ratio>=0.8:near.append(dict(a=a['doc_id'],b=b['doc_id'],similarity=round(ratio,4)))
 required=['doc_id','scenic','text_type','source_name','source_url','original_text','clean_text']
 checks=dict(required_missing={k:sum(not str(r.get(k,'')).strip() for r in accepted) for k in required},
  missing_original_web_url=sum(not r['original_url'] for r in accepted if r['text_type']=='游客游记'),
  duplicate_doc_ids=len(accepted)-len({r['doc_id'] for r in accepted}),
  exact_duplicate_clean_text=len(accepted)-len({r['clean_text'] for r in accepted}),
  near_duplicate_pairs_threshold_0_8=near,
  remaining_html=sum(bool(re.search(r'</?[A-Za-z][^>]*>',r['clean_text'])) for r in accepted),
  replacement_characters=sum(r['clean_text'].count('\ufffd') for r in accepted),
  whitespace_format_violations=sum(bool(re.search(r'\r|[ \t]{2,}|^ | $|\n\n',r['clean_text'])) for r in accepted),
  idempotence_failures=sum(clean_text(r['clean_text'])[0]!=r['clean_text'] for r in accepted),
  remaining_known_promotional_tails=sum(bool(re.search(r'特色:全程使用2\+1|请详细说明您要咨询的问题|文下可扫二维码关注|携程攻略社区!|\(图文:@',r['clean_text'])) for r in accepted),
  sufficient_per_scenic=all(x['official_documents']>=1 and x['travel_documents']>=5 for x in counts))
 report=dict(input_records=len(raw),output_records=len(accepted),rejected=reject,counts=counts,
  original_chars=sum(r['original_chars'] for r in accepted),clean_chars=sum(r['clean_chars'] for r in accepted),
  changed_records=sum(x['changed'] for x in audit),rule_occurrences=dict(rule_count),checks=checks,
  python=platform.python_version(),executable=sys.executable,scan_manifest='data/source/manifest.json',
  limitation='语料原平台URL缺失；游记分类为内容判断；18条目的抽样不能代表整体旅游语料；历史费用、开放状态与不当行为不应直接用于Agent建议')
 dump(OUT/'quality_report.json',report)
 samples=[]
 for doc_id in ['HS-O01','HS-T01','HS-T04','JZG-O01','ZJJ-T05']:
  r=next(x for x in accepted if x['doc_id']==doc_id)
  samples.append(dict(doc_id=doc_id,original_excerpt=r['original_text'][:450],clean_excerpt=r['clean_text'][:450],original_chars=r['original_chars'],clean_chars=r['clean_chars']))
 dump(OUT/'before_after_samples.json',samples)
 # Independent semantic preservation checks on real official route material.
 by={r['doc_id']:r for r in accepted}
 assert '7:00-8:10' in by['JZG-O01']['clean_text'] and '13:30-14:20' in by['JZG-O01']['clean_text']
 assert '→' in by['JZG-O01']['clean_text'] and '—' in by['HS-O01']['clean_text']
 assert checks['sufficient_per_scenic'] and checks['idempotence_failures']==0
 assert checks['remaining_known_promotional_tails']==0
 assert all(v==0 for v in checks['required_missing'].values())
 # Read CSV back and compare to JSONL, so embedded newlines and quoting are verified.
 with (OUT/'cleaned_data.csv').open(encoding='utf-8-sig',newline='') as f:back=list(csv.DictReader(f))
 assert [x['clean_text'] for x in back]==[x['clean_text'] for x in accepted]
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
