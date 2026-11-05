"""Offline fusion of current labs 1--5. Character offsets are zero-based/end-exclusive."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,csv,json,hashlib,re
import networkx as nx
from enrichment import local_modes,enrich
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/lab6'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def uid(kind,*parts):return kind+':'+hashlib.sha256(json.dumps(parts,ensure_ascii=False).encode()).hexdigest()[:20]
def readcsv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def validate_entities(docs,entities):
 for e in entities:
  d=docs[e['doc_id']]
  if e['scenic']!=d['scenic'] or d['clean_text'][e['start']:e['end']]!=e['text']:raise ValueError('Entity offset mismatch: '+e['doc_id'])
class Fusion:
 def __init__(self):
  self.rules=load(ROOT/'data/lab6/rules.json');self.g=nx.MultiDiGraph();self.ev={};self.audit=[];self.align=[];self.ca=[];self.aa=[]
 def evidence(self,file,record,**kw):
  d=dict(file=file,record=str(record),**kw);i=uid('evidence',d);self.ev[i]=dict(id=i,**d);return i
 def node(self,i,typ,label,scenic,refs,**kw):
  if i not in self.g:self.g.add_node(i,type=typ,label=label,scenic=scenic,evidence_refs=[],aliases=[],**kw)
  d=self.g.nodes[i];d['evidence_refs']=sorted(set(d['evidence_refs'])|set(refs));return i
 def edge(self,u,v,typ,refs,**kw):
  i=uid('edge',u,v,typ,{} if typ=='USES' else kw)
  if self.g.has_edge(u,v,i):self.g[u][v][i]['evidence_refs']=sorted(set(self.g[u][v][i]['evidence_refs'])|set(refs))
  else:self.g.add_edge(u,v,key=i,id=i,type=typ,evidence_refs=sorted(set(refs)),**kw)
 def identity(self,scenic,typ,raw):
  n=raw.strip()
  if typ=='POI':
   n=self.rules['aliases'].get(scenic,{}).get(n,n)
   if n in self.rules['ambiguous'].get(scenic,[]):return None,n,'ambiguous'
   typ='Transport' if n in self.rules['transport'] else ('Scenic' if n==scenic else 'Place')
  elif typ=='TRANSPORT':typ='Transport'
  if typ=='Transport':n=self.rules['transport_aliases'].get(n,n)
  return uid(typ,scenic,n),n,typ
 def scenic(self,s,refs):return self.node(uid('Scenic',s,s),'Scenic',s,s,refs,scope='corpus_scope_not_physical_boundary')
 def entity(self,s,typ,raw,refs):
  i,n,t=self.identity(s,typ,raw)
  if i is None:
   self.audit.append(dict(category='ambiguous',scenic=s,surface=raw,decision='quarantine',refs=refs));return None
  self.node(i,t,n,s,refs);self.g.nodes[i]['aliases']=sorted(set(self.g.nodes[i]['aliases'])|{raw})
  if t!='Scenic':self.edge(self.scenic(s,refs),i,'HAS_ENTITY',refs,semantics='corpus_membership')
  return i
 def run(self):
  paths=['outputs/cleaned_data.jsonl','outputs/cleaned_data.csv','data/raw/selected_raw.jsonl','outputs/quality_report.json','outputs/cleaning_audit.csv','outputs/lab2/entities.json','outputs/lab2/iteration.json','outputs/lab3/structured_routes.json','outputs/lab3/time_hierarchy.json','outputs/lab3/route_compare.json','data/lab3/processed/scenic_dataset.json','outputs/lab4/candidates.jsonl','outputs/lab4/full_review.csv','outputs/lab5/mapping.json','data/lab6/rules.json','src/lab6/enrichment.py']
  self.manifest={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
  try:rows=[json.loads(x) for x in (ROOT/paths[0]).read_text(encoding='utf-8-sig').splitlines() if x.strip()];source=paths[0]
  except json.JSONDecodeError as ex:
   rows=readcsv(ROOT/paths[1]);source=paths[1];self.audit.append(dict(category='invalid_jsonl',file=paths[0],error=str(ex),decision='verified_csv_fallback'))
  self.docs={d['doc_id']:d for d in rows}
  if len(self.docs)!=len(rows) or len(rows)!=18:raise ValueError('Duplicate/missing documents')
  raw={d['doc_id']:d for d in map(json.loads,(ROOT/'data/raw/selected_raw.jsonl').read_text(encoding='utf8').splitlines())}
  for d in rows:
   if hashlib.sha256(d['clean_text'].encode()).hexdigest()!=d['content_sha256'] or d['original_text']!=raw[d['doc_id']]['original_text']:raise ValueError('Source hash mismatch')
  (ROOT/'data/lab6/documents_snapshot.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf8')
  self.source=source;self.ents=load(ROOT/'outputs/lab2/entities.json')['entities'];validate_entities(self.docs,self.ents)
  self.by_doc=defaultdict(list);self.targets={}
  for e in self.ents:
   d=self.docs[e['doc_id']];self.by_doc[e['doc_id']].append(e)
   ref=self.evidence('outputs/lab2/entities.json',f"{e['doc_id']}:{e['start']}:{e['end']}",doc_id=e['doc_id'],scenic=e['scenic'],start=e['start'],end=e['end'],text=e['text'],source_kind='official' if d['text_type']=='官方路线' else 'tourist',source_url=d.get('original_url') or None,source_record_id=d['source_record_id'],source_file=d['source_file'],text_sha256=d['content_sha256'])
   typ='Time' if e['type']=='TIME' else e['type'];i=self.entity(e['scenic'],typ,e['text'],[ref]);self.targets[(e['doc_id'],e['start'],e['end'])]=i
   self.align.append(dict(input='lab2',scenic=e['scenic'],surface=e['text'],statistical_canonical=e['canonical'],node_id=i,evidence_ref=ref))
  routes=load(ROOT/'outputs/lab3/structured_routes.json');hier={r['scenic']:r for r in load(ROOT/'outputs/lab3/time_hierarchy.json')};self.route_records=[]
  if {r['scenic'] for r in routes}!={'黄山','九寨沟','张家界'}:raise ValueError('Wrong lab3 version')
  for ix,r in enumerate(routes):
   s=r['scenic'];rid='route:'+s;ref=self.evidence('outputs/lab3/structured_routes.json',str(ix),scenic=s,source_kind='official_curated',source_url=r['url'],source_name=r['source'],text=r['text'])
   self.node(rid,'Route',s+'实验三官方整理路线',s,[ref]);self.edge(self.scenic(s,[ref]),rid,'HAS_ROUTE',[ref]);prev=None
   periods={st['step_no']:b['period'] for b in hier[s]['periods'] for st in b['steps']}
   seq=[]
   for st in r['steps']:
    k=st['step_no'];step=rid+f':step:{k:02d}';sr=self.evidence('outputs/lab3/structured_routes.json',f'{ix}/steps/{k-1}',scenic=s,source_kind='official_curated',text=st['raw_segment'],source_url=r['url'])
    self.node(step,'Step',f"{k:02d} {st['spot']}",s,[sr],route_id=rid,order=k,activity=st['activity'],activity_status='upstream_rule_not_independently_verified')
    self.edge(rid,step,'HAS_STEP',[sr],order=k)
    if prev:self.edge(prev,step,'NEXT',[sr],semantics='upstream_text_order_not_verified_road')
    prev=step;target=self.entity(s,'POI',st['spot'],[sr]);self.edge(step,target,'USES' if self.g.nodes[target]['type']=='Transport' else 'AT',[sr]);seq.append(st['spot'])
    self.align.append(dict(input='lab3',scenic=s,surface=st['spot'],step_id=step,node_id=target,evidence_ref=sr))
    for mode,a,b,rule in local_modes(r,st):
     mr=self.evidence('outputs/lab3/structured_routes.json',f'{ix}/text/{a}:{b}',scenic=s,source_kind='official_curated',start=a,end=b,text=r['text'][a:b],source_url=r['url'],rule=rule)
     mt=self.entity(s,'TRANSPORT',mode,[mr]);self.edge(step,mt,'USES',[mr])
    period=st['time_period'];t=self.entity(s,'Time',period,[sr]);self.edge(step,t,'DURING',[sr],status='upstream_parse')
    if periods.get(k) is not None and periods.get(k)!=period:
     hp=periods.get(k);hr=self.evidence('outputs/lab3/time_hierarchy.json',f'{s}/{k}',scenic=s,source_kind='heuristic',text=hp)
     tt=self.entity(s,'Time',hp,[hr]);self.edge(step,tt,'DURING',[hr],status='conflicting_hierarchy_heuristic')
     self.audit.append(dict(category='time_conflict',scenic=s,step=k,parse=period,hierarchy=hp,decision='retain_both'))
   enrich(self,r,rid)
   missing=sorted({st['step_no'] for st in r['steps']}-set(periods))
   if missing:self.audit.append(dict(category='missing_hierarchy_steps',scenic=s,steps=missing,decision='retain_parse_without_fabricating_hierarchy'))
   self.route_records.append(dict(route_id=rid,scenic=s,sequence=seq))
  comp=load(ROOT/'outputs/lab3/route_compare.json');self.audit.append(dict(category='lab3_tourist_demo',scenic=comp['scenic'],decision='comparison_evidence_only_not_real_tourist_route',note='TOURIST_NOTE is embedded in upstream code',metrics=comp['metrics']))
  dataset=load(ROOT/'data/lab3/processed/scenic_dataset.json');self.audit.append(dict(category='lab3_unassigned_notes',count=len(dataset['travel_notes']),decision='not_assigned_without_scenic_route_evidence'))
  reviews={x['id']:x for x in readcsv(ROOT/'outputs/lab4/full_review.csv')}
  for c in map(json.loads,(ROOT/'outputs/lab4/candidates.jsonl').read_text(encoding='utf8').splitlines()):
   gold=reviews[c['id']];text=self.docs[c['doc_id']]['clean_text'];decision='quarantine';target=None
   if text[c['pronoun_start']:c['pronoun_end']]!=c['pronoun']:raise ValueError('Coref position mismatch')
   if gold['status']=='resolved' and gold['gold_type']=='POI' and c['prediction']==gold['gold_antecedent']:
    target=self.targets.get((c['doc_id'],c['prediction_start'],c['prediction_end']))
    if target:
     ref=self.evidence('outputs/lab4/candidates.jsonl',c['id'],scenic=c['scenic'],doc_id=c['doc_id'],start=c['pronoun_start'],end=c['pronoun_end'],text=c['pronoun'],antecedent=c['prediction'],source_kind='coref_reviewed',review_file='outputs/lab4/full_review.csv')
     self.g.nodes[target]['evidence_refs'].append(ref);decision='attach_evidence'
   self.ca.append(dict(id=c['id'],decision=decision,node_id=target,prediction=c['prediction'],gold=gold))
  for m in load(ROOT/'outputs/lab5/mapping.json'):
   refs=[];targets=set()
   for z in m['sources']:
    d=self.docs[z['doc_id']]
    for k in ['condition','advice']:
     if d['clean_text'][z[k+'_start']:z[k+'_end']]!=z[k]:raise ValueError('Advice position mismatch')
    ref=self.evidence('outputs/lab5/mapping.json',z['id'],scenic=m['scenic'],doc_id=z['doc_id'],source_kind='official' if z['text_type']=='官方路线' else 'tourist',condition=z['condition'],advice=z['advice'],condition_start=z['condition_start'],condition_end=z['condition_end'],advice_start=z['advice_start'],advice_end=z['advice_end'],source_url=d.get('original_url') or None,source_file=d['source_file'],source_record_id=d['source_record_id']);refs.append(ref)
    for e in self.by_doc[z['doc_id']]:
     if any(z[k+'_start']<=e['start'] and e['end']<=z[k+'_end'] for k in ['condition','advice']):
      target=self.targets[(e['doc_id'],e['start'],e['end'])]
      if target:targets.add(target)
   reason=self.rules['exclude_advice'].get(m['mapping_id'])
   if m['needs_context_resolution']:reason='unresolved_reference'
   if reason:self.aa.append(dict(mapping_id=m['mapping_id'],decision='quarantine',reason=reason,refs=refs));continue
   s=m['scenic'];ci=uid('Condition',s,m['condition']);ai='advice:'+m['mapping_id']
   self.node(ci,'Condition',m['condition'],s,refs,condition_type=m['condition_type'],traveler_type=m['traveler_type']);self.node(ai,'Advice',m['advice'],s,refs,mapping_id=m['mapping_id'],historical_only=True,negative=bool(re.search('不坐|不要|放弃|不建议',m['advice'])))
   self.edge(self.scenic(s,refs),ci,'HAS_CONDITION',refs);self.edge(ci,ai,'RECOMMENDS',refs,condition=m['condition'],advice=m['advice'],traveler_type=m['traveler_type'],condition_type=m['condition_type'])
   for t in sorted(targets):self.edge(ai,t,'MENTIONS',refs,semantics='text_mention_not_recommend_visit')
   self.aa.append(dict(mapping_id=m['mapping_id'],decision='include',targets=sorted(targets),refs=refs))
  for i,d in self.g.nodes(data=True):
   d['evidence_refs']=sorted(set(d['evidence_refs']));es=[self.ev[x] for x in d['evidence_refs']];mentions=[x for x in es if x['file']=='outputs/lab2/entities.json'];d['mention_count']=len(mentions);d['document_count']=len({x['doc_id'] for x in mentions});d['official_mentions']=sum(x['source_kind']=='official' for x in mentions);d['tourist_mentions']=sum(x['source_kind']=='tourist' for x in mentions);d['source_kinds']=sorted({x['source_kind'] for x in es});d['support_class']='multi_document' if d['document_count']>1 else 'single_document_or_route'
   if len(mentions)==1:self.audit.append(dict(category='low_frequency',node_id=i,label=d['label'],scenic=d['scenic'],decision='keep_with_evidence'))
  self.data=dict(schema_version='1',directed=True,multigraph=True,nodes=[dict(id=i,**d) for i,d in sorted(self.g.nodes(data=True))],edges=[dict(source=u,target=v,**d) for u,v,k,d in sorted(self.g.edges(keys=True,data=True))])
 def write(self,out=OUT):
  out=Path(out);out.mkdir(parents=True,exist_ok=True)
  for f,x in [('graph',self.data),('schema',self.rules['schema']),('diagnostics',self.audit),('alignment',self.align),('advice_audit',self.aa),('coref_audit',self.ca),('routes',self.route_records),('input_manifest',dict(files=self.manifest,text_source=self.source,documents=len(self.docs),entities=len(self.ents)))]:dump(out/(f+'.json'),x)
  (out/'evidence.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for k,v in sorted(self.ev.items())),encoding='utf8')
  for name,rows in [('nodes',self.data['nodes']),('edges',self.data['edges'])]:
   with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=sorted({k for row in rows for k in row}));w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
  flat=nx.MultiDiGraph();scalar=lambda d:{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) or v is None else v for k,v in d.items()}
  for n,d in self.g.nodes(data=True):flat.add_node(n,**scalar(d))
  for u,v,k,d in self.g.edges(keys=True,data=True):flat.add_edge(u,v,key=k,**scalar(d))
  nx.write_graphml(flat,out/'graph.graphml')
  stats=dict(nodes=len(self.g),edges=self.g.number_of_edges(),by_node_type=dict(Counter(d['type'] for _,d in self.g.nodes(data=True))),by_edge_type=dict(Counter(d['type'] for *_,d in self.g.edges(data=True))),weak_components=nx.number_weakly_connected_components(self.g),isolates=len(list(nx.isolates(self.g))),by_scenic={s:sum(d['scenic']==s for _,d in self.g.nodes(data=True)) for s in ['黄山','九寨沟','张家界']},advice=dict(Counter(x['decision'] for x in self.aa)),coref=dict(Counter(x['decision'] for x in self.ca)),diagnostics=dict(Counter(x['category'] for x in self.audit)),networkx=nx.__version__)
  dump(out/'stats.json',stats);print(json.dumps(stats,ensure_ascii=False))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args();f=Fusion();f.run();f.write(a.output)
if __name__=='__main__':main()
