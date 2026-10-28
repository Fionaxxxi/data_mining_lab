"""Archived Word report generator; not part of the current Markdown workflow."""
from pathlib import Path
from copy import deepcopy
import json,zipfile,hashlib,re
from lxml import etree as E
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=Path(__file__).resolve().parent
TEMPLATE=ARCHIVE/'report/template_original.docx'
q=json.loads((ROOT/'outputs/quality_report.json').read_text(encoding='utf-8'))
rows=[json.loads(x) for x in (ROOT/'outputs/cleaned_data.jsonl').read_text(encoding='utf-8').splitlines()]
by={r['doc_id']:r for r in rows}
sections=[]
def sec(title,parts):sections.append((title,parts))
sec('1.1 实验目标与数据准备',[
'本实验围绕景区游览指南的程序性知识挖掘，完成多源文本的数据准备、清洗、结构化保存和质量检查。清洗结果保留景点、交通方式、时间表达及游览顺序，为后续实体识别、路线层级解析、共指消解和条件建议抽取提供统一输入。',
'数据采用公开语料与官网补充材料的混合方式，不编写或运行网页爬虫。游客游记来自用户指定的ModelScope数据集BAAI/IndustryCorpus2，读取tourism_geography/chinese下high/rank_00130.parquet与middle/rank_00712.parquet两个分片，分别含21,401条和187,404条记录，共208,805条。实验只使用这两个分片，未扫描整个数据集。分片路径、文件大小、SHA-256及记录数量见data/source/manifest.json。',
'原语料实际包含text、_id、industry_type、quality_score及若干质量统计字段。其中text为正文，_id为原记录标识，industry_type为行业标签，quality_score为数据集已有质量分，不是本实验评价分。先按景区及攻略、路线、游记等词筛出候选，再对正文中的本人或同行者游览经历、具体景点和行程信息进行LLM辅助逐条内容复核，最终目的抽样选择黄山、九寨沟、张家界各5篇游记。文章开头偶然提及景区、主体为其他地区或纯百科新闻的材料不计入。该抽样用于教学实验，不代表整体语料分布，也未核验原作者身份。',
'原语料不含原网页URL，不能仅凭正文口吻判定为官方。因此另从黄山旅游官方平台、九寨沟景区官方网站及湖南省文化和旅游厅公开页面补充路线材料，各景区整理为1份官方路线指南，共3份；同一指南可能含多条备选路线，不将其拆成多篇游记。黄山和九寨沟保留原HTML快照，张家界因直接下载连接失败，采用已阅读核验官方页面的人工摘录，保留URL、标题及摘录范围。',
('table','表1-1 最终数据组成',['景区','官方指南份数','游客游记篇数','合计'],[[x['scenic'],str(x['official_documents']),str(x['travel_documents']),'6'] for x in q['counts']]+[['总计','3','15','18']]),
'官方补充来源：[1] 黄山旅游官方平台《黄山风景区清明假期常见旅游咨询》第20问，https://wap.huangshan.com.cn/detail/strategy/fjqlyzx；[2] 九寨沟景区《游玩方式》的一日精华游部分，https://www.jiuzhai.com/intelligent-service/way-of-play；[3] 湖南省文化和旅游厅《直达武陵源 乐享张家界——武陵源自驾游精品线路推荐》中的景区自驾一日游部分，https://whhlyt.hunan.gov.cn/whhlyt/wldhlylx/202208/t20220816_27584140.html。访问与整理日期为2026年10月28日。',
])
sec('1.2 清洗方法与实现流程',[
'处理流程为：加载Parquet分片并按固定记录定位 → 整理18份原始材料为JSONL → 批量清洗 → 检查字段、空值及重复 → 导出CSV与JSONL → 生成审计记录与质量报告。prepare_data.py负责原记录定位及官方节选整理；run_lab1.py负责离线清洗与检查。selected_raw.jsonl保留选中材料的原始内容，不覆盖原文。',
'HTML处理：仅在检测到实际标签时使用BeautifulSoup解析，删除script、style与noscript节点，把段落、换行和本次官网使用的font块映射为换行，再提取正文。黄山官网正文存放于页面脚本的JSON字段内，先解析该字段，再取第20问对应的原HTML段落；不能直接删除页面脚本，否则会丢失整段指南。',
'噪声处理：删除语料中的“图片发自简书app”占位文字；识别责任编辑、本篇游记统计、平台免责声明等明确尾部标记，截断后面的网页推荐与互动内容。复查还发现JZG-T01正文结束后拼接旅游产品广告，JZG-T05末尾含转载声明、公众号及平台推广，针对其明确边界补充尾部规则；删除末尾图文署名及明确来源、原标题、地址与电话元数据行。原始来源字段保留在结构化记录中，正文网址清理不影响来源追溯。未命中明确规则的文字不推测性删除。',
'格式统一：统一CRLF/CR为LF，解码HTML实体，清除零宽和控制字符，将全角ASCII字符转换为半角，压缩行内重复空白，去除行首尾空白和空行。保留中文逗号与英文逗号的混用，不进行全局标点替换；保留箭头、长横线、序号、数字、时间和计量单位。未做分词、停用词删除或自动纠错，避免损伤后续路线与实体信息。',
'异常处理：清洗正文为空、景区或类型不在允许值内的记录进入拒绝清单；对清洗正文计算SHA-256进行完全去重并保留首条。相同景区、相同文本类型的记录两两计算SequenceMatcher字符序列相似度，阈值为0.80，仅用于近重复复核提示，不自动删除相似路线。对替换字符U+FFFD及可疑改写词另行检查，不猜测修复原意。本次18条输入均保留。',
'本项目独立环境为D:\\miniconda3\\envs\\dm_scenic_lab，实际Python版本为3.11.18。运行时使用该环境的python.exe，不使用base或其他项目环境。核心依赖为pyarrow 26.0.0、beautifulsoup4 4.15.0；锁定版本见requirements.txt。',
'离线复现：在项目根目录运行 & D:\\miniconda3\\envs\\dm_scenic_lab\\python.exe .\\src\\run_lab1.py 。输入为data/raw/selected_raw.jsonl，输出目录为outputs。若需从原Parquet重建选中材料，先运行src/prepare_data.py，再运行清洗入口。完整命令和下载说明见README.md。',
])
field_rows=[
['doc_id','字符串','HS/JZG/ZJJ景区前缀；O为官方指南，T为游记；项目内唯一'],
['scenic / text_type','字符串','景区；官方路线或游客游记'],
['source_name / source_url','字符串','数据集或官方发布平台名称及入口URL'],
['original_url','字符串','原网页URL；15篇语料游记为空，官方材料填官网URL'],
['source_file / source_record_id','字符串','原分片或快照/摘录文件；语料_id或官方节选标识'],
['source_row_index','整数或null','Parquet分片内从0开始的行号；官方材料为null'],
['title / acquired_date','字符串','游记为首行截取摘要，非核验原标题；官方为页面/节选标题；整理日期'],
['original_text / clean_text','字符串','选中原文（官网可为原HTML节选）与清洗后正文'],
['quality_score','数值或null','原语料已有质量分；官方补充未评分'],
['provenance_status / classification_basis / scope_note','字符串','来源核验状态、类型判断依据及范围/历史性说明'],
['original_chars / clean_chars / content_sha256','整数/字符串','清洗前后Python字符长度；清洗文本SHA-256'],
]
sec('1.3 结构化数据设计',[
'数据以一份完整的选中游记或一份官方指南节选为一条记录。CSV使用UTF-8 BOM与标准引号转义，正文内换行保留；JSONL使用UTF-8，每行一个JSON对象，便于后续批处理。两份输出包含同一批18条记录和一致的正文。',
('table','表1-2 实际输出字段设计',['字段','类型','含义'],field_rows),
'“官方路线”依据发布机构和官网域名核验；“游客游记”依据文章内容中的游览经历判定，并在provenance_status中明确原发布者和网页未核验。source_url为数据集入口不等于原文链接，original_url缺失保持为空，绝不补造。原语料的64位_id按字符串保存，避免Excel打开时出现科学计数法或精度丢失；在Excel导入CSV时应将该列指定为文本。',
'后续实验可用doc_id关联数据，以clean_text作为识别文本。实体字符位置须基于这一版清洗文本记录；若继续修改清洗规则，应重新生成实体位置，不能混用原文和清洗文本的偏移。',
])
hs1=by['HS-T01'];jzg=by['JZG-O01'];hs4=by['HS-T04'];zjj=by['ZJJ-T05']
idx=hs1['original_text'].find('图片发自简书app')
before=hs1['original_text'][max(0,idx-22):idx+65]
after=re.sub(r' +',' ',before.replace('图片发自简书app',''))
sec('1.4 清洗前后对比与数据质量',[
f'本次输入18条、输出18条，无删除记录；其中{q["changed_records"]}条正文发生变化，{q["output_records"]-q["changed_records"]}条未命中需修改的规则并原样保留。清洗前原始字段共{q["original_chars"]:,}个字符，清洗后共{q["clean_chars"]:,}个字符，减少{q["original_chars"]-q["clean_chars"]:,}个字符。原始字段中含HTML，因此该变化只能说明标签及噪声减少，不能直接解释为正文信息损失率。',
('table','表1-3 自动质量检查结果',['检查项','结果','检查方式'],[
['景区及类型覆盖','3个景区，各1份官方指南+5篇游记','按scenic和text_type分组计数'],
['核心字段缺失','0','检查7个必填字段是否为空白'],
['游记原网页URL缺失','15/15','单独统计original_url，不与数据集入口混淆'],
['文档ID重复 / 完全重复正文','0 / 0','ID集合检查 / 清洗正文SHA-256'],
['近重复候选','0对','同景区同类型；字符序列相似度≥0.80'],
['残留HTML / U+FFFD','0 / 0','标签模式检查 / 替换字符计数'],
['空白格式违规 / 清洗幂等失败','0 / 0','检查CR、连续空白；再次清洗结果应不变'],
['已知广告尾部残留','0','检查产品广告、咨询框、平台/公众号推广和末尾署名特征'],
['CSV读回一致性','18条正文均一致','CSV读回后逐条对比JSONL正文'],
]),
f'例1，HS-T01，语料_id={hs1["source_record_id"]}，清洗前{hs1["original_chars"]}字符、清洗后{hs1["clean_chars"]}字符。原文片段：“{before}”；清洗后对应片段：“{after}”。删除图片占位文字，保留“因为提前买了一日团”等行程正文。',
'例2，JZG-O01，原HTML片段为 <font style="font-size:18px">        沟口乘车→原始森林（7:00-8:10    一个小时车程）</font>；清洗后为“沟口乘车→原始森林(7:00-8:10 一个小时车程)”。HTML标签和重复空白被去除，全角括号统一，箭头、景点、起止时间和车程文字保留。程序还验证了13:30-14:20这一时间段未丢失。',
f'例3，HS-T04，原文{hs4["original_chars"]}字符，清洗后{hs4["clean_chars"]}字符。原网页尾部从“[责任编辑:紫荆蓝]”开始，后续含与旅游无关的推荐标题，按明确尾部标记整体截去；截断之前的黄山游览正文保留。例4，ZJJ-T05删除单独的客栈地址与电话元数据行，原始行仍可在original_text中复核。',
f'实际命中规则包括：{q["rule_occurrences"].get("html_removed",0)}条材料去除HTML，{q["rule_occurrences"].get("image_placeholder_removed",0)}次图片占位文字删除，{q["rule_occurrences"].get("web_tail_removed",0)}次网页尾部截断，{q["rule_occurrences"].get("metadata_line_removed",0)}条元数据行删除，{q["rule_occurrences"].get("author_credit_removed",0)}次末尾署名删除，{q["rule_occurrences"].get("fullwidth_ascii_normalized",0)}条材料发生全角ASCII归一化。未命中的网址删除、控制字符与明显乱码规则仍保留在代码中，但不把它们写成本批数据已经出现的问题。',
'详细证据见outputs/cleaning_audit.csv、before_after_samples.json、scenic_counts.csv和quality_report.json。检查结果由run_lab1.py实际计算，数量以文件为准，不以截图替代数据。',
])
sec('1.5 问题与分析',[
'问题一：行业标签与景区名只能筛出候选，不能保证主题正确。筛选中发现一篇文章开头提到以后想去张家界，正文实际是德天瀑布、通灵峡谷和涠洲岛自驾游。若仅按关键词命中就收录，会造成景区错配。处理时依据正文主题、实际到访与行程景点复核，排除该记录（原_id=499700012157），不将其计入最终18条。',
'问题二：语料缺少原网页来源，官方身份无法验证。采用混合来源补齐官方材料，语料记录保留分片名、原_id、从0计的分片行号及文件哈希；15篇游记的原URL仍为空。张家界官方页面可检索阅读，但直接保存HTML连接失败，因此保留人工摘录文本并明确其证据形态，不声称已下载完整网页。',
'问题三：原文包含历史性、主观性和潜在错误信息。例如HS-T05涉及2009年行程及翻越封闭位置的叙述，HS-T04含投喂猴子的经历，JZG-T02含逃票叙述；这些属于待研究文本，不是本实验赞成的建议。清洗阶段不把原文事实擅自改写，审计中标记可疑行为；后续条件建议抽取与Agent应用应过滤不当行为，并重新核验票价、开放状态等时效信息。',
'问题四：官方文本也可能有时间冲突。JZG-O01最后一段写“17:00-17:35”，前一段结束时间为17:20，存在重叠；本实验保留原文，不把推测改正写入数据。路线层级实验应标注冲突，不能将所有时间直接当作可靠调度约束。张家界官网页面发布时间为2022-08-16，文末署名日期为2021-09-18，两者不混为一谈。',
'问题五：跨景区行程与来源迁移说明仍需下游判断。张家界游记含黄龙洞、天门山及凤凰古城等行程；九寨沟游记也可能包含重庆、成都等沿途地点。为保留上下文，本实验按整篇保留并在scope_note注明范围，后续实体和路线抽取必须区分核心景区、外围景点和交通城市，不能把整篇所有地点都归为同一景区内部节点。',
'最终输出可供后续实验直接按doc_id、scenic、text_type读取clean_text。18条记录满足每景区至少1份官方路线和5篇游客游记的数据数量安排；本实验完成的是基础数据工程，不宣称已完成实体识别、路线解析或建议抽取。内容筛选及报告整理使用LLM辅助，关键清洗逻辑、实际输入输出和程序检查均可复现；本次未以小样本结果估计整体语料准确率。',
])
md=['# 实验一 景区指南数据采集与预处理','以下内容对应所提供报告模板的1.1—1.5节；个人信息及小组贡献按实际情况填写。','']
for title,parts in sections:
 md+=['## '+title,'']
 for part in parts:
  if isinstance(part,tuple):
   _,caption,heads,data=part;md +=[caption,'','| '+' | '.join(heads)+' |','| '+' | '.join(['---']*len(heads))+' |']
   md+=['| '+' | '.join(row)+' |' for row in data];md+=['']
  else:md +=[part,'']
(ARCHIVE/'report/实验一可粘贴内容.md').write_text('\n'.join(md),encoding='utf-8')
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';NS={'w':W}
def tag(x):return '{'+W+'}'+x
with zipfile.ZipFile(TEMPLATE) as z:
 xml=E.fromstring(z.read('word/document.xml'));body=xml.find('w:body',NS)
 paras=body.findall('w:p',NS)
 text=lambda p:''.join(p.itertext()) if False else ''.join(p.xpath('.//w:t/text()',namespaces=NS))
 start=next(p for p in paras if text(p).startswith('1.1 ')); end=next(p for p in paras if text(p).startswith('—实验项目2'))
 # Preserve the next chapter title and its leading page-break/title paragraph.
 end_index=body.index(end)-2
 stop=body[end_index]
 body_sample=next(p for p in paras if text(p).startswith('（说明数据将'))
 heading_sample=deepcopy(start)
 def pnode(s,heading=False):
  p=deepcopy(heading_sample if heading else body_sample)
  for c in list(p):
   if c.tag!=tag('pPr'):p.remove(c)
  pr=p.find(tag('pPr'))
  # Text slots flow naturally; no manual page padding from the empty template.
  for c in list(pr):
   if c.tag in [tag('pageBreakBefore'),tag('spacing')]:pr.remove(c)
  spacing=E.SubElement(pr,tag('spacing'));spacing.set(tag('after'),'100' if heading else '80')
  if heading: E.SubElement(pr,tag('keepNext'))
  r=E.SubElement(p,tag('r'))
  if heading:
   rp=E.SubElement(r,tag('rPr'));color=E.SubElement(rp,tag('color'));color.set(tag('val'),'000000')
  t=E.SubElement(r,tag('t'));t.text=s;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
  if s.startswith('表1-'):E.SubElement(pr,tag('keepNext'))
  return p
 def table(heads,data):
  tb=E.Element(tag('tbl'));pr=E.SubElement(tb,tag('tblPr'));width=E.SubElement(pr,tag('tblW'));width.set(tag('w'),'9300');width.set(tag('type'),'dxa')
  borders=E.SubElement(pr,tag('tblBorders'))
  for side in ['top','left','bottom','right','insideH','insideV']:
   b=E.SubElement(borders,tag(side));b.set(tag('val'),'single');b.set(tag('sz'),'4');b.set(tag('color'),'D9D9D9')
  widths=[1800,2600,2900,2000] if len(heads)==4 else ([4100,1000,4200] if heads[0]=='字段' else [2600,3000,3700])
  grid=E.SubElement(tb,tag('tblGrid'))
  for w in widths:E.SubElement(grid,tag('gridCol')).set(tag('w'),str(w))
  for i,row in enumerate([heads]+data):
   tr=E.SubElement(tb,tag('tr'))
   trpr=E.SubElement(tr,tag('trPr'));E.SubElement(trpr,tag('cantSplit'))
   if i==0:E.SubElement(trpr,tag('tblHeader'))
   for ci,value in enumerate(row):
    tc=E.SubElement(tr,tag('tc'));tp=E.SubElement(tc,tag('tcPr'))
    cw=E.SubElement(tp,tag('tcW'));cw.set(tag('w'),str(widths[ci]));cw.set(tag('type'),'dxa')
    if i==0:
     sh=E.SubElement(tp,tag('shd'));sh.set(tag('fill'),'E7E6E6')
    margins=E.SubElement(tp,tag('tcMar'))
    for side in ['top','left','bottom','right']:
     m=E.SubElement(margins,tag(side));m.set(tag('w'),'85');m.set(tag('type'),'dxa')
    va=E.SubElement(tp,tag('vAlign'));va.set(tag('val'),'center')
    p=pnode(value);tc.append(p)
    if i==0:
     rp=E.Element(tag('rPr'));p.find(tag('r')).insert(0,rp);E.SubElement(rp,tag('b'))
     E.SubElement(p.find(tag('pPr')),tag('keepNext'))
  return tb
 new=[]
 for title,parts in sections:
  new.append(pnode(title,True))
  for part in parts:
   if isinstance(part,tuple):new.extend([pnode(part[1]),table(part[2],part[3])])
   else:new.append(pnode(part))
 a=body.index(start);b=body.index(stop)
 # Narrow edit only: no section-property paragraphs occur in these slots.
 assert not any(n.xpath('.//w:sectPr',namespaces=NS) for n in list(body)[a:b])
 for n in list(body)[a:b]:body.remove(n)
 for i,n in enumerate(new):body.insert(a+i,n)
 out=ARCHIVE/'report/探索性实验报告_已填实验一.docx'
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as zz:
  for info in z.infolist():zz.writestr(deepcopy(info),E.tostring(xml,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
 with zipfile.ZipFile(out) as zz:
  unchanged=[i.filename for i in z.infolist() if i.filename!='word/document.xml' and z.read(i.filename)==zz.read(i.filename)]
  assert len(unchanged)==len(z.infolist())-1
 proof=dict(template_sha256=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),changed_package_parts=['word/document.xml'],unchanged_package_parts=len(unchanged),output=str(out),scope='Only experiment 1 content; cover, grading, contribution, chapters 2-8 unchanged')
 (ARCHIVE/'qa/report_preservation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
