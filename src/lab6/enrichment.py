"""Bounded-clause transport and explicitly labelled alternate-source context."""
import re
from collections import Counter

def core(name):
 return re.sub(r'\([^)]*\)','',name).replace('景观区','')

def local_modes(route,step):
 """Accept a facility step or a named place and ride verb in the SAME clause.

 Source text is read directly, never the upstream parser's oversized raw_segment.
 Returns (mode, start, end, rule) spans within the lab3 route text.
 """
 text=route['text'];place=core(step['spot']);modes=[]
 names=['百龙天梯','云谷索道','玉屏索道','太平索道','天子山索道','观光车','步行']
 for clause in re.finditer(r'[^，,；;。→]+',text):
  value=clause.group()
  for mode in names:
   if mode not in value:continue
   facility=(place==mode)
   # A place merely appearing in an adjoining enumeration does not inherit a ride.
   specific=(mode.startswith(place) and len(place)>=3)
   if (facility or specific) and re.search(r'乘|索道|天梯|上行|下行',value):
    modes.append((mode,clause.start(),clause.end(),'same_named_facility_clause'))
 return sorted(set(modes))

def enrich(f,r,rid):
 """Different official routes can provide context, never overwrite route timing.

 Join only an explicit arrow-line endpoint, a lab2 exact entity span, and a
 uniquely occurring lab3 step identity. No nearest-entity or whole-document join.
 """
 scenic=r['scenic'];counts=Counter(f.identity(scenic,'POI',s['spot'])[0] for s in r['steps'])
 for doc in f.docs.values():
  if doc['scenic']!=scenic or doc['text_type']!='官方路线':continue
  text=doc['clean_text']
  for line in re.finditer(r'[^\n]+',text):
   if '→' not in line.group():continue
   head=line.group().split('(')[0];head_end=line.start()+len(head)
   endpoints=[e for e in f.by_doc[doc['doc_id']] if e['type']=='POI' and line.start()<=e['start'] and e['end']<=head_end]
   attrs=[e for e in f.by_doc[doc['doc_id']] if e['type'] in ['TIME','TRANSPORT'] and line.start()<=e['start'] and e['end']<=line.end()]
   for st in r['steps']:
    identity=f.identity(scenic,'POI',st['spot'])[0]
    if counts[identity]!=1:continue  # repeated occurrences cannot be timed by name alone
    matched=[e for e in endpoints if f.targets[(e['doc_id'],e['start'],e['end'])]==identity]
    if not matched:continue
    for e in attrs:
     target=f.targets[(e['doc_id'],e['start'],e['end'])]
     if not target:continue
     ref=f.evidence('outputs/cleaned_data.csv',f"{doc['doc_id']}:{line.start()}:{line.end()}",scenic=scenic,doc_id=doc['doc_id'],start=line.start(),end=line.end(),text=line.group(),source_kind='official_context',source_url=doc.get('original_url'),endpoint=e['text'],join_place=matched[0]['text'])
     typ='SOURCE_TIME' if e['type']=='TIME' else 'SOURCE_TRANSPORT'
     f.edge(rid+f":step:{st['step_no']:02d}",target,typ,[ref],status='alternate_official_route_context',source_doc=doc['doc_id'],source_start=line.start(),source_end=line.end(),semantics='whole_arrow_segment_not_lab3_schedule',endpoint=matched[0]['text'])
     f.audit.append(dict(category='source_context_join',relation=typ,step=st['step_no'],scenic=scenic,source_doc=doc['doc_id'],start=line.start(),end=line.end(),attribute=e['text'],decision='context_only'))
