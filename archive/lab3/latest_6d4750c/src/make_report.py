# -*- coding: utf-8 -*-
"""生成实验三报告 Word 文档（黄山/九寨沟/张家界）。"""
import os, json
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
FIG = os.path.join(ROOT, "figures")

doc = Document()
style = doc.styles["Normal"]
style.font.name = "宋体"
style.font.size = Pt(11)
try:
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
except Exception:
    pass


def h(text, level=1):
    doc.add_heading(text, level=level)


def para(text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    return p


def add_table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, hh in enumerate(headers):
        t.rows[0].cells[i].text = hh
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
    return t


title = doc.add_heading("《数据挖掘》探索性实验报告\n实验项目3：游览路线的层级结构挖掘（黄山/九寨沟/张家界）", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# 1 目的
h("一、实验目的", 1)
para("本实验面向程序性文本（景区游览指南/游客游记），完成三项任务："
     "①分析官方推荐路线的文本描述模式，设计解析规则，将每条路线转换为统一的结构化表示"
     "（含步骤序号、时间、景点POI、活动等字段）；②基于解析结果构建以时间（上午/中午/下午）"
     "为维度的游览层级结构；③选取同一景区的官方推荐路线与游客游记中隐含的实际路线，"
     "在景点覆盖度、顺序一致性、时间分配等维度进行量化对比，并分析差异原因。"
     "本实验覆盖黄山、九寨沟、张家界三个景区。")

# 2 环境
h("二、实验环境与依赖", 1)
para("Python 3.13；主要依赖：requests、beautifulsoup4、lxml（爬虫与网页解析），"
     "pandas、pyarrow（读取教师数据集 parquet），matplotlib（可视化），python-docx（报告）。"
     "完整依赖见 requirements.txt。运行入口：python run.py。")

# 3 数据采集
h("三、数据采集与数据集", 1)
para("本实验采用两路采集 + 官方路线样本，三类数据互补：", bold=True)
add_table(
    ["数据来源", "采集方式", "说明"],
    [
        ["爬虫采集", "requests+BeautifulSoup",
         "实际抓取九寨沟官网(jiuzhai.com)、张家界市政府(zjj.gov.cn)、红网张家界(zjj.rednet.cn)官方页面"],
        ["教师数据集", "modelscope BAAI/IndustryCorpus2",
         "住宿餐饮酒店中文语料，28431行中按旅游关键词命中3999行，抽样40条旅游叙述语料"],
        ["官方路线样本", "官网/权威导览整理",
         "黄山取自黄山风景区管委会官网《黄山一日游》线路一；九寨沟、张家界依据官方导览整理"],
    ],
)
para("说明：黄山风景区官网(cnhuangshan.com)存在较严格反爬，故黄山官方路线采用黄山风景区管理委员会"
     "官网(hsgwh.huangshan.gov.cn)公开的“黄山一日游”线路文本；九寨沟、张家界由爬虫直接抓取官方站点。"
     "教师数据集为行业通用网页语料，本实验仅抽取其中与景区游览相关的片段作为游客叙述补充。")

# 4 解析
h("四、官方路线的描述模式分析与结构化解析", 1)
h("4.1 三种典型描述模式", 2)
add_table(
    ["模式", "特征", "本实验样本"],
    [
        ["箭头链路 arrow_chain", "用 → 串联景点：南大门 → 云谷寺 → …", "黄山（管委会线路一）"],
        ["编号列表 numbered", "用 1. 2. 3. 罗列：1.沟口；2.树正群海…", "九寨沟"],
        ["时间分段 time_segmented", "按 上午…中午…下午… 叙述", "张家界武陵源"],
    ],
)
h("4.2 解析规则", 2)
para("(1) 格式识别：优先识别编号列表，其次箭头链路，最后时间分段。")
para("(2) 步骤抽取：箭头链路按 → 切分并处理括号内并列子景点（如 天海景观区（鳌鱼峰）拆出 天海+鳌鱼峰）；"
     "编号列表用正则 (\\d+)[.、] 提取；时间分段按时段锚点切分后再抽取“从X、乘Y、游Z”等景点。")
para("(3) 字段统一：每步输出 step_no、time_period、spot（归一化后）、activity、raw_segment。")
h("4.3 名称归一化", 2)
para("建立别名/全称→规范名映射，如 云谷索道→云谷寺索道(交通)、黄山南大门→南大门(入口)、"
     "武陵源门票站→武陵源门票站(出口)、出沟→沟口(出口)；并剥离“景观区/索道上行/进山/上袁家界”等粘连词，"
     "对相邻重复景点去重。")

routes = json.load(open(os.path.join(OUT, "structured_routes.json"), encoding="utf-8"))
h("4.4 解析结果", 2)
for r in routes:
    para("【%s】声明格式=%s，识别格式=%s，共%d步" %
         (r["scenic"], r["expected_format"], r["detected_format"], len(r["steps"])), bold=True)
    add_table(["序号", "时段", "景点POI", "活动"],
              [[s["step_no"], s["time_period"], s["spot"], s["activity"]] for s in r["steps"]])

# 5 时间层级
h("五、时间维度层级结构构建", 1)
para("在原文中定位时段锚点（上午/中午/下午/傍晚）的字符位置，把有序景点按位置归入对应时段；"
     "针对“先列景点、句尾才说明时间安排”的箭头链路/编号列表，采用比例分配策略按时段切分；"
     "同一时段内重复景点仅保留首次出现。")
hier = json.load(open(os.path.join(OUT, "time_hierarchy.json"), encoding="utf-8"))
for hh in hier:
    para("【%s】" % hh["scenic"], bold=True)
    for pb in hh["periods"]:
        para("  [%s] %d站：%s" % (pb["period"], len(pb["steps"]),
             " → ".join(s["spot"] for s in pb["steps"])))
if os.path.exists(os.path.join(FIG, "time_hierarchy.png")):
    doc.add_picture(os.path.join(FIG, "time_hierarchy.png"), width=Inches(6.3))
    doc.add_paragraph("图1 三个景区的游览时间层级结构").alignment = WD_ALIGN_PARAGRAPH.CENTER

# 6 对比
h("六、官方路线与游客实际路线对比", 1)
para("以黄山为例，从一篇游客游记文本中按出现顺序抽取游客实际POI序列，与官方路线对比。")
cmp = json.load(open(os.path.join(OUT, "route_compare.json"), encoding="utf-8"))
para("官方路线（%d站）：%s" % (len(cmp["official_seq"]), " → ".join(cmp["official_seq"])))
para("游客实际路线（%d站）：%s" % (len(cmp["tourist_seq"]), " → ".join(cmp["tourist_seq"])))
m = cmp["metrics"]
add_table(
    ["对比维度", "数值", "说明"],
    [
        ["景点覆盖度", "%.1f%%" % (m["coverage"]*100), "游客走到的官方景点占官方总数比例"],
        ["顺序一致性(LCS)", "%.1f%%" % (m["order_consistency"]*100), "最长公共子序列占比，衡量顺序吻合度"],
        ["游客遗漏景点", "、".join(m["missing_in_tourist"]) or "无", "游客未停留的官方景点"],
        ["时间分配(上/中/下)", "官方%s vs 游客%s" % (cmp["time_allocation"]["official_am_noon_pm"], cmp["time_allocation"]["tourist_am_noon_pm"]), "游客在莲花峰捷径上省时"],
    ],
)
if os.path.exists(os.path.join(FIG, "route_compare.png")):
    doc.add_picture(os.path.join(FIG, "route_compare.png"), width=Inches(6.0))
    doc.add_paragraph("图2 官方路线与游客实际路线对比（黄山）").alignment = WD_ALIGN_PARAGRAPH.CENTER

h("6.1 差异原因分析", 2)
para("(1) 覆盖度：游客为看日出和节省体力，直接从云谷索道上白鹅岭看日出，未专门在云谷寺停留；"
     "又因时间有限选择莲花峰捷径，跳过排云亭、散花坞，且直接坐玉屏索道下山未走慈光阁，"
     "故遗漏4站（覆盖66.7%）。")
para("(2) 顺序一致性：游客整体沿南大门→始信峰→狮子峰→天海→鳌鱼峰→玉屏楼迎客松的官方主干动线行进，"
     "LCS=88.9%，说明官方线路设计与游客实际动线高度吻合；差异主要来自个别支线取舍而非顺序颠倒。")
para("(3) 时间分配：官方站点在上午/中午/下午均分[5,4,5]，游客因中途看日出和山顶用餐时间压缩，"
     "各时段[3,3,3]更均衡——体现游客按兴趣和体力弹性分配停留时长，而官方按线路覆盖均摊。")

# 7 名称归一化与稳健性
h("七、名称归一化、噪声处理与稳健性", 1)
para("· 全称/简称：云谷寺景观区→云谷寺、黄山南大门→南大门(入口)、武陵源门票站→武陵源门票站(出口)；")
para("· 粘连处理：剥离“景观区/索道上行/索道下行/进山/上袁家界/出沟”等尾部动词；")
para("· 括号子景点：把“天海景观区（鳌鱼峰）”“狮子峰景观区（清凉台、散花坞）”拆为并列景点；")
para("· 过对齐风险：映射表仅覆盖已知景点，未命中词保留原文，避免误合并；")
para("· 局限：纯规则解析对自由句式鲁棒性有限，时间比例分配为启发式近似，后续可结合LLM做语义解析。")

# 8 可复现性
h("八、可复现性说明", 1)
para("运行：pip install -r requirements.txt 后执行 python run.py。")
para("输入：data/processed/scenic_dataset.json（统一数据集）。")
para("输出：output/structured_routes.json（结构化步骤）、time_hierarchy.json（时间层级）、"
     "route_compare.json（对比指标）；figures/ 下两张可视化图。")
para("关键中间结果：crawler/scenic_crawler.py 输出 data/raw/crawled_pages.json；"
     "load_industrycorpus.py 输出 data/processed/industrycorpus_tourism_sample.json。")

# 9 运行结果截图
h("九、运行结果截图", 1)
para("在实验环境执行 python run.py 完整流程（爬虫采集→数据集加载→汇总→路线解析→时间层级→官方/游客对比），"
     "退出码为 0。以下为运行结果截图，完整记录了各阶段的关键输出：", )
if os.path.exists(os.path.join(FIG, "run_screenshot.png")):
    doc.add_picture(os.path.join(FIG, "run_screenshot.png"), width=Inches(6.5))
    doc.add_paragraph("图3 实验三运行结果截图（python run.py 全流程）").alignment = WD_ALIGN_PARAGRAPH.CENTER
para("截图关键信息：爬虫成功采集九寨沟(50段)/张家界(63段)/红网张家界(84段)，黄山官网被反爬拦截（如实记录）；"
     "教师数据集命中旅游关键词3999行、抽样40条；黄山14步/九寨沟11步/张家界5步；"
     "时间层级[黄山5/4/4、九寨沟4/3/4、张家界3/2]；官方-游客对比覆盖66.7%、顺序一致88.9%。")

# 10 问题与解决办法
h("十、实验过程中遇到的问题及解决办法", 1)
para("（完整明细见工程内《实验过程问题及解决办法.md》）本次实验主要遇到以下 9 类问题及其解决办法：", )
add_table(
    ["阶段", "问题", "解决办法"],
    [
        ["数据采集", "黄山官网(cnhuangshan.com)反爬，黄山市府返回412",
         "放弃直接抓取，改用黄山风景区管理委员会官网权威“黄山一日游”线路文本，并在报告中标注来源URL"],
        ["数据采集", "马蜂窝等游记社区202/403反爬，无法稳定采集",
         "游记叙述改用教师数据集IndustryCorpus2按旅游关键词过滤抽样；官方信息以可稳定访问的官网为爬虫来源"],
        ["路线解析", "正则字符类 r\"[→->]\" 报 bad character range",
         "改为分支 r\"→|->\" 显式匹配中文箭头与英文->"],
        ["路线解析", "先 strip 丢右括号，括号子景点(天海景观区(鳌鱼峰))无法拆分",
         "调整顺序：先匹配提取括号内并列子景点，再对主名strip"],
        ["路线解析", "同一景点不同环节重复(玉屏楼→迎客松→玉屏楼；天子山×2)",
         "步骤列表相邻重复去重并重排step_no；时间层级对同一时段内重复景点再次去重"],
        ["路线解析", "景点名粘连动作词(出沟/进山/上袁家界/百龙天梯)",
         "建立TRAILING_SEG剥离表循环去尾部动词，再经NAME_NORMALIZE映射为规范名"],
        ["路线解析", "编号列表与箭头链路格式混淆(括号内含→)",
         "调整格式识别优先级为 编号列表>箭头链路>时间分段"],
        ["时间层级", "箭头/编号路线景点先于时段说明出现，时段分桶全归上午",
         "检测景点整体先于首锚点时，改用比例分配策略按时段数量对有序景点均分"],
        ["可视化", "Consolas字体无中文字形，运行日志截图中文全缺",
         "改用系统中文字体(Microsoft YaHei)渲染日志，重新生成截图"],
    ],
)

doc.save(os.path.join(ROOT, "实验三_游览路线层级结构挖掘_报告.docx"))
print("报告已生成:", os.path.join(ROOT, "实验三_游览路线层级结构挖掘_报告.docx"))
