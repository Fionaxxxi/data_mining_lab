"""Deterministic full-route projection; no remote assets or force-layout label collisions."""
import os
from pathlib import Path
from build import ROOT,OUT,load,dump
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'outputs/maintenance/mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
from matplotlib import font_manager
from query import read_graph,query

def main():
 for font in [Path('C:/Windows/Fonts/msyh.ttc'),Path('C:/Windows/Fonts/simhei.ttf')]:
  if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name();break
 plt.rcParams['svg.fonttype']='none';plt.rcParams['axes.unicode_minus']=False
 out=OUT/'figures';out.mkdir(exist_ok=True);g=read_graph();steps=query(g,dict(kind='route',scenic='九寨沟'))
 fig,ax=plt.subplots(figsize=(22,16));fig.patch.set_facecolor('#fafaf7');ax.set_facecolor('#fafaf7');ax.set_xlim(0,22);ax.set_ylim(-1,16);ax.axis('off')
 ax.text(.4,15.55,'九寨沟完整路线知识网络',fontsize=25,weight='bold',color='#172b3a')
 ax.text(.4,15.08,'实验三全部11步 · 实验二官方/游客提及支持 · 时间冲突保留 · 历史文本知识',fontsize=12,color='#51616d')
 colors={'Step':'#e7eaf0','Place':'#d8ece5','Time':'#fae8bc','Transport':'#dce8f7','Condition':'#e9dff3','Advice':'#f2e1d7'}
 def box(x,y,w,h,label,color,fontsize=10):
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.04,rounding_size=.09',facecolor=color,edgecolor='#8a999f',linewidth=.8))
  ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=fontsize,color='#203744')
 def arrow(x,y,xx,yy,label='',c='#607d88'):
  ax.add_patch(FancyArrowPatch((x,y),(xx,yy),arrowstyle='-|>',mutation_scale=12,color=c,linewidth=1.2))
  if label:ax.text((x+xx)/2,(y+yy)/2+.06,label,fontsize=8,color=c,ha='center')
 box(.4,14.05,2.4,.55,'Scenic 九寨沟','#b7d8dc');box(5.9,14.05,3.4,.55,'Route 官方整理一日游','#c8d5e3');arrow(2.85,14.32,5.85,14.32,'HAS_ROUTE')
 ys=[]
 for j,st in enumerate(steps):
  y=12.9-j*.91;ys.append(y)
  box(1,y,1.4,.48,f"Step {st['order']:02d}",colors['Step'])
  if j:arrow(1.7,ys[j-1]-.02,1.7,y+.51,'NEXT')
  places=[t for t in st['targets'] if t['type']=='AT'];name=places[0]['label'] if places else '交通步骤'
  en=query(g,dict(kind='entity',scenic='九寨沟',name=name));n=en[0] if en else {}
  box(4,y,3.2,.48,name,colors['Place'],11);arrow(2.45,y+.24,3.95,y+.24,'AT')
  ax.text(7.4,y-.06,f"官方提及 {n.get('official_mentions',0)} / 游客提及 {n.get('tourist_mentions',0)}",fontsize=9,color='#4a6861')
  times=[t for t in st['targets'] if t['type']=='DURING'];labels=[]
  for t in times:labels.append(t['label']+('（层级推断）' if t['status']=='conflicting_hierarchy_heuristic' else '（解析）'))
  box(10.8,y-.04,4.1,.56,'Time '+' / '.join(labels),colors['Time'],9);arrow(2.45,y+.62,10.75,y+.62,'DURING')
  contexts=[t for t in st['targets'] if t['type'] in ['SOURCE_TIME','SOURCE_TRANSPORT']]
  clocks=sorted(set(t['label'] for t in contexts if t['type']=='SOURCE_TIME' and ':' in t['label']))
  transport=sorted(set(t['label'] for t in contexts if t['type']=='SOURCE_TRANSPORT'))
  if contexts:
   label='另一官方原文段（非本路线时刻）\n'+' / '.join(clocks)+'\n'+' / '.join(transport)
   box(15.5,y-.08,5.7,.72,label,colors['Transport'],8)
   ax.plot([2.4,2.65,15.2,15.2],[y+.05,y-.24,y-.24,y+.24],color='#668ca2',linewidth=.8,linestyle=':')
   arrow(15.2,y+.24,15.45,y+.24,'',c='#668ca2')
  modes=[t['label'] for t in st['targets'] if t['type']=='USES']
  if modes:box(15.5,y-.04,2,.56,'交通\n'+'/'.join(modes),colors['Transport'],8);arrow(14.95,y+.24,15.45,y+.24,'USES')
 # HAS_STEP is represented once as a bracket over the entire complete step column.
 ax.plot([.6,.6],[ys[-1],ys[0]+.5],color='#81949b',linewidth=1);ax.text(.35,8.5,'HAS_STEP\n全部11步',rotation=90,ha='center',fontsize=9,color='#607d88')
 arrow(6.1,14.0,2.2,13.45,'HAS_STEP')
 # Return gate remains a separate occurrence linked to the same entity.
 ax.text(.5,2.55,'第01步和第11步均对齐“沟口”；保留两次出现，不将路线折叠为自环。',fontsize=11,color='#285750')
 ax.text(.5,2.13,'黄框：实验三时段证据；蓝框：实验一另一官方路线原文段，不能解释为本路线时间表。',fontsize=10,color='#78612c')
 ax.text(.5,1.7,'图例  灰：步骤   绿：地点   黄：时间   蓝：交通/另一原文上下文    蓝色虚线：SOURCE_TIME / SOURCE_TRANSPORT（来源上下文）',fontsize=11)
 ax.text(.5,1.28,'投影范围：完整官方路线；实体来源频次投影为地点属性。全量实体/条件与证据保存在 graph.json。',fontsize=10,color='#51616d')
 ax.text(.5,.85,'未画游客全部时间表达和逐条来源，以避免遮挡；未从实体共现推断游客行走顺序。',fontsize=10,color='#51616d')
 fig.savefig(out/'jiuzhaigou_full.svg',bbox_inches='tight');fig.savefig(out/'jiuzhaigou_full.png',dpi=140,bbox_inches='tight');plt.close(fig)
 # Conditional subnetwork preserves negative advice as text rather than positive visit edges.
 adv=query(g,dict(kind='advice',scenic='九寨沟',contains='体力'))
 fig,ax=plt.subplots(figsize=(15,5));ax.axis('off');ax.set_xlim(0,15);ax.set_ylim(0,5)
 ax.text(.3,4.5,'九寨沟条件建议子网络',fontsize=21,weight='bold')
 for i,a in enumerate(adv):
  y=3.3-i*1.2
  ax.text(.5,y,'Condition\n'+a['condition'],fontsize=12,bbox=dict(boxstyle='round,pad=.5',fc=colors['Condition'],ec='#9d8ca4'))
  ax.annotate('',xy=(7,y+.1),xytext=(5,y+.1),arrowprops=dict(arrowstyle='->',color='#6d5c78'));ax.text(5.1,y+.35,'RECOMMENDS',fontsize=10)
  ax.text(7.3,y,'Advice\n'+a['advice'],fontsize=11,bbox=dict(boxstyle='round,pad=.5',fc=colors['Advice'],ec='#bba99f'))
 ax.text(.3,.3,'原文条件及否定保留；这些是历史文本建议，需要另核验当前信息。',fontsize=11)
 fig.savefig(out/'conditions.svg',bbox_inches='tight');fig.savefig(out/'conditions.png',dpi=140,bbox_inches='tight');plt.close(fig)
 dump(out/'view_manifest.json',dict(scenic='九寨沟',visible_step_ids=[s['step_id'] for s in steps],projection='complete official route steps; entity source counts as attributes',hidden='non-route entities, full provenance and condition network (separate detail)',not_verified='current travel feasibility'))
 print('Full scenic view:',len(steps),'steps; condition detail:',len(adv))
if __name__=='__main__':main()
