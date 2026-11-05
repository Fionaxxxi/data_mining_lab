"""Read-only graph queries; JSON input/output, no online tourism assertions."""
import argparse,json
from pathlib import Path
from build import ROOT,OUT,load,dump
import networkx as nx
def read_graph(path=OUT/'graph.json'):
 data=load(path);g=nx.MultiDiGraph()
 for n in data['nodes']:g.add_node(n['id'],**{k:v for k,v in n.items() if k!='id'})
 for e in data['edges']:g.add_edge(e['source'],e['target'],key=e['id'],**{k:v for k,v in e.items() if k not in ['source','target']})
 return g
def query(g,request):
 s=request.get('scenic');kind=request.get('kind')
 if kind=='route':
  rid='route:'+str(s)
  if rid not in g:return []
  steps=sorted([(v,g.nodes[v]) for u,v,d in g.out_edges(rid,data=True) if d['type']=='HAS_STEP'],key=lambda x:x[1]['order'])
  return [dict(step_id=i,order=d['order'],label=d['label'],activity=d['activity'],targets=[dict(type=e['type'],label=g.nodes[v]['label'],evidence_refs=e['evidence_refs'],status=e.get('status')) for u,v,e in g.out_edges(i,data=True) if e['type'] in ['AT','USES','DURING','SOURCE_TIME','SOURCE_TRANSPORT']],evidence_refs=d['evidence_refs']) for i,d in steps]
 if kind=='entity':return [dict(id=i,**d) for i,d in g.nodes(data=True) if d['scenic']==s and (request['name']==d['label'] or request['name'] in d['aliases'])]
 if kind=='advice':
  return [dict(d,mapping_id=g.nodes[v]['mapping_id']) for u,v,d in g.edges(data=True) if d['type']=='RECOMMENDS' and g.nodes[u]['scenic']==s and request.get('contains','') in (g.nodes[u]['label']+g.nodes[v]['label'])]
 if kind=='centrality':
  # Site corpus hub degrees would be meaningless; rank route-place projection only.
  p=nx.DiGraph()
  for u,v,d in g.edges(data=True):
   if d['type']=='NEXT' and g.nodes[u]['scenic']==s:
    a=[x for _,x,e in g.out_edges(u,data=True) if e['type']=='AT'];b=[x for _,x,e in g.out_edges(v,data=True) if e['type']=='AT']
    for x in a:
     for y in b:p.add_edge(x,y)
  return [dict(label=g.nodes[n]['label'],degree=d) for n,d in sorted(p.degree,key=lambda x:(-x[1],g.nodes[x[0]]['label']))[:5]]
 raise ValueError('Unsupported query kind')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--request',help='JSON request');a=ap.parse_args();g=read_graph()
 requests=[json.loads(a.request)] if a.request else [dict(kind='route',scenic='九寨沟'),dict(kind='entity',scenic='九寨沟',name='诺日朗中心站'),dict(kind='entity',scenic='黄山',name='排云亭'),dict(kind='advice',scenic='九寨沟',contains='体力'),dict(kind='centrality',scenic='黄山'),dict(kind='route',scenic='不存在')]
 results=[dict(input=r,result=query(g,r)) for r in requests]
 if not a.request:dump(OUT/'queries.json',results)
 print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
