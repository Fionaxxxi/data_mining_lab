"""Independent export validation, reference cases, and negative mutation tests."""
import copy,json,hashlib
from pathlib import Path
from collections import Counter
import networkx as nx
from build import ROOT,OUT,load,dump,Fusion,validate_entities
from query import read_graph,query

def structural(data,schema,evidence):
 ns={x['id']:x for x in data['nodes']}
 if len(ns)!=len(data['nodes']):raise ValueError('duplicate node')
 for e in data['edges']:
  if e['source'] not in ns or e['target'] not in ns:raise ValueError('dangling edge')
  a,b=ns[e['source']],ns[e['target']];allowed=schema[e['type']]
  if a['type'] not in allowed[0] or b['type'] not in allowed[1]:raise ValueError('bad endpoint type')
  if a['scenic']!=b['scenic']:raise ValueError('cross scenic edge')
  if e['type']=='NEXT' and (a['route_id']!=b['route_id'] or b['order']!=a['order']+1):raise ValueError('bad route order')
  if not e['evidence_refs'] or any(x not in evidence for x in e['evidence_refs']):raise ValueError('missing edge evidence')
 for n in ns.values():
  if not n['evidence_refs'] or any(x not in evidence for x in n['evidence_refs']):raise ValueError('missing node evidence')
 return True

def main():
 data=load(OUT/'graph.json');schema=load(OUT/'schema.json');ev={e['id']:e for e in map(json.loads,(OUT/'evidence.jsonl').read_text(encoding='utf8').splitlines())};g=read_graph();checks={}
 checks['structure_and_evidence']=structural(data,schema,ev)
 checks['three_components_no_isolates']=nx.number_weakly_connected_components(g)==3 and not list(nx.isolates(g))
 original=load(ROOT/'outputs/lab3/structured_routes.json')
 for r in original:
  got=query(g,dict(kind='route',scenic=r['scenic']))
  checks['complete_order:'+r['scenic']]=len(got)==len(r['steps']) and [x['label'].split(' ',1)[1] for x in got]==[s['spot'] for s in r['steps']]
 f=Fusion();f.run()
 checks['deterministic_rebuild']=f.data==data
 checks['input_hashes_unchanged']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in load(OUT/'input_manifest.json')['files'].items())
 docs=f.docs;checks['all_2015_entity_offsets']=len(f.ents)==2015
 validate_entities(docs,f.ents)
 for a,b,s in [('诺日朗中心站','诺日朗换乘站','九寨沟'),('武陵源东门','武陵源景区东门','张家界')]:checks['align:'+a]=f.identity(s,'POI',a)[0]==f.identity(s,'POI',b)[0]
 for a,b,t,s in [('西海大峡谷','西海大峡谷谷底','POI','黄山'),('珍珠滩','珍珠滩瀑布','POI','九寨沟'),('云谷索道','太平索道','TRANSPORT','黄山')]:checks['distinct:'+a]=f.identity(s,t,a)[0]!=f.identity(s,t,b)[0]
 checks['cross_scenic_names_distinct']=f.identity('黄山','POI','南门')[0]!=f.identity('张家界','POI','南门')[0]
 low=query(g,dict(kind='entity',scenic='黄山',name='白鹅山庄'));checks['single_occurrence_keep']=len(low)==1 and low[0]['mention_count']==1
 checks['ambiguous_quarantined']=not query(g,dict(kind='entity',scenic='九寨沟',name='诺日朗'))
 ladder=query(g,dict(kind='entity',scenic='张家界',name='百龙天梯'));checks['ladder_transport']=len(ladder)==1 and ladder[0]['type']=='Transport'
 hs=query(g,dict(kind='route',scenic='黄山'));checks['return_gate_two_steps_one_identity']=hs[0]['step_id']!=hs[-1]['step_id'] and [t['label'] for t in hs[0]['targets'] if t['type']=='AT']==[t['label'] for t in hs[-1]['targets'] if t['type']=='AT']
 aa={x['mapping_id']:x for x in load(OUT/'advice_audit.json')};checks['advice_negative_cases']=all(aa[x]['decision']=='quarantine' for x in ['C002','C003','C007','C008','C019','C022','C023','C030'])
 checks['advice_positive_cases']=all(aa[x]['decision']=='include' for x in ['C001','C017','C024','C025','C028'])
 ca={x['id']:x for x in load(OUT/'coref_audit.json')};checks['reviewed_coref']=ca['HS-T02:444']['decision']=='attach_evidence' and ca['JZG-T02:366']['decision']=='quarantine'
 checks['empty_query']=query(g,dict(kind='route',scenic='不存在'))==[]
 gm=nx.read_graphml(OUT/'graph.graphml');checks['graphml_roundtrip']=len(gm)==len(g) and gm.number_of_edges()==g.number_of_edges()
 # Every retained span must resolve independently in the frozen CSV text snapshot.
 spans=0
 for e in ev.values():
  if e.get('doc_id'):
   d=docs[e['doc_id']]['clean_text']
   if e['file']=='outputs/lab5/mapping.json':
    for k in ['condition','advice']:
     assert d[e[k+'_start']:e[k+'_end']]==e[k];spans+=1
   elif e.get('start') is not None:
    assert d[e['start']:e['end']]==e['text'];spans+=1
 checks['all_evidence_spans']=True
 # Inject corrupt inputs/edges: these must fail, rather than passing a self-consistent build.
 mutation={}
 bad=copy.deepcopy(data);bad['edges'][0]['target']='missing'
 try:structural(bad,schema,ev);mutation['dangling_edge']=False
 except ValueError:mutation['dangling_edge']=True
 bad=copy.deepcopy(data);e=next(e for e in bad['edges'] if e['type']=='NEXT');e['target']=next(n['id'] for n in bad['nodes'] if n['type']=='Step' and n['scenic']!='九寨沟' and n['id']!=e['source'] and n['route_id']!=next(x['route_id'] for x in bad['nodes'] if x['id']==e['source']))
 try:structural(bad,schema,ev);mutation['cross_route_next']=False
 except ValueError:mutation['cross_route_next']=True
 ents=copy.deepcopy(f.ents);ents[0]['start']+=1
 try:validate_entities(docs,ents);mutation['wrong_span']=False
 except ValueError:mutation['wrong_span']=True
 try:query(g,dict(kind='unsupported'));mutation['invalid_query']=False
 except ValueError:mutation['invalid_query']=True
 checks.update({'reject:'+k:v for k,v in mutation.items()})
 # All graph steps must be represented in the complete scenic figure.
 fig=load(OUT/'figures/view_manifest.json');jzg=[n['id'] for n in data['nodes'] if n['type']=='Step' and n['scenic']=='九寨沟'];checks['full_scenic_figure_coverage']=set(jzg)==set(fig['visible_step_ids'])
 # Versioned semantic regression cases: the previous tests missed these errors.
 uses=[e for e in data['edges'] if e['type']=='USES'];nodes={n['id']:n for n in data['nodes']}
 checks['semantic:no_ladder_on_gate_or_stream']=not any(e['source'] in ['route:张家界:step:01','route:张家界:step:02'] and nodes[e['target']]['label']=='百龙天梯' for e in uses)
 checks['semantic:one_ladder_on_own_step']=sum(e['source']=='route:张家界:step:03' and nodes[e['target']]['label']=='百龙天梯' for e in uses)==1
 checks['semantic:no_duplicate_uses']=len({(e['source'],e['target']) for e in uses})==len(uses)
 contexts=[e for e in data['edges'] if e['type'] in ['SOURCE_TIME','SOURCE_TRANSPORT']]
 checks['semantic:jzg_time_context']=any(nodes[e['source']]['scenic']=='九寨沟' and e['type']=='SOURCE_TIME' for e in contexts)
 checks['semantic:jzg_transport_context']=any(nodes[e['source']]['scenic']=='九寨沟' and e['type']=='SOURCE_TRANSPORT' for e in contexts)
 checks['semantic:context_not_schedule']=all(e['status']=='alternate_official_route_context' and e['semantics']=='whole_arrow_segment_not_lab3_schedule' for e in contexts)
 checks['semantic:explicit_context_endpoints']=all(e['endpoint'] in docs[e['source_doc']]['clean_text'][e['source_start']:e['source_end']].split('(')[0] for e in contexts)
 checks['semantic:no_context_on_repeated_gate']=not any(e['source'] in ['route:九寨沟:step:01','route:九寨沟:step:11'] for e in contexts)
 source_spans=0
 for e in ev.values():
  if e['file']=='outputs/lab3/structured_routes.json' and e.get('start') is not None:
   ix=int(e['record'].split('/')[0]);assert original[ix]['text'][e['start']:e['end']]==e['text'];source_spans+=1
 checks['semantic:lab3_clause_spans']=source_spans>0
 result=dict(passed=all(checks.values()),checks=checks,evidence_spans_checked=spans,mutation_tests=mutation,method='export reader + fixed positive/negative cases + independent source spans; implemented and executed by same assistant, no independent human review')
 dump(OUT/'acceptance.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
