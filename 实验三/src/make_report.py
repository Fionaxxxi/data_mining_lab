# -*- coding: utf-8 -*-
"""生成实验三报告 Word 文档。"""
import os, json
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
FIG = os.path.join(ROOT, "figures")

doc = Document()
# 全局中文字体
style = doc.styles["Normal"]
style.font.name = "宋体"
style.font.size = Pt(11)
try:
    from docx.oxml.ns import qn
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
except Exception:
    pass


def h(text, level=1):
    p = doc.add_heading(text, level=level)
    return p


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


# ===== 封面标题 =====
title = doc.add_heading("《数据挖掘》探索性实验报告\n实验项目3：游览路线的层级结构挖掘", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# ===== 1 实验目的 =====
h("一、实验目的", 1)
para("本实验面向程序性文本（景区游览指南/游客游记），完成三项任务："
     "①分析官方推荐路线的文本描述模式，设计解析规则，将每条路线转换为统一的结构化表示"
     "（含步骤序号、时间、景点POI、活动等字段）；②基于解析结果构建以时间"
     "（上午/中午/下午）为维度的游览层级结构；③选取同一景区的官方推荐路线与游客游记中"
     "隐含的实际路线，在景点覆盖度、顺序一致性、时间分配等维度进行量化对比，并分析差异原因。")

# ===== 2 环境与依赖 =====
h("二、实验环境与依赖", 1)
para("Python 3.13；主要依赖：requests、beautifulsoup4、lxml（爬虫与网页解析），"
     "pandas、pyarrow（读取教师数据集 parquet），matplotlib（可视化）。"
     "完整依赖见 requirements.txt。运行入口：python run.py。")

# ===== 3 数据采集 =====
h("三、数据采集与数据集", 1)
para("本实验采用两路采集 + 官方导览整理样本，三类数据互补：", bold=True)
add_table(
    ["数据来源", "采集方式", "说明"],
    [
        ["爬虫采集", "requests+BeautifulSoup", "实际抓取故宫博物院官网(dpm.org.cn)等页面，获得开放时间08:30-17:00、周一闭馆、参观须知等官方信息"],
        ["教师数据集", "modelscope BAAI/IndustryCorpus2", "住宿餐饮酒店中文语料，28431行中按旅游关键词命中10422行，抽样40条旅游叙述语料"],
        ["官方路线样本", "依据官网导览整理", "覆盖箭头链路/编号列表/时间分段三种描述格式，对应故宫、颐和园、西湖三个景区"],
    ],
)
para("说明：马蜂窝等社区站存在反爬（返回202验证页），故爬虫以可稳定访问的官方站点为主；"
     "教师数据集为行业通用网页语料，本实验仅抽取其中与景区游览相关的片段作为游客叙述补充。")

# ===== 4 官方路线结构化解析 =====
h("四、官方路线的描述模式分析与结构化解析", 1)
h("4.1 三种典型描述模式", 2)
add_table(
    ["模式", "特征", "本实验样本"],
    [
        ["箭头链路 arrow_chain", "用 → 串联景点：午门 → 太和殿 → …", "故宫中轴线一日游"],
        ["编号列表 numbered", "用 1. 2. 3. 罗列：1.仁寿殿；2.玉澜堂…", "颐和园东宫门路线"],
        ["时间分段 time_segmented", "按 上午…中午…下午… 叙述", "西湖环湖一日游"],
    ],
)
h("4.2 解析规则", 2)
para("(1) 格式识别：优先识别编号列表（避免括号内“邀月门→排云门”被误判为箭头链路），"
     "其次识别箭头链路，最后识别时间分段。")
para("(2) 步骤抽取：箭头链路按 → 切分；编号列表用正则 (\\d+)[.、] 提取；"
     "时间分段按 上午/中午/下午/傍晚 锚点切分后再抽取“从X、经Y、至Z、登W”等景点。")
para("(3) 字段统一：每步输出 step_no（序号）、time_period（时段）、spot（景点POI，归一化后）、"
     "activity（活动动词）、raw_segment（原始片段）。")
h("4.3 名称归一化", 2)
para("建立别名/俗称→规范名映射表，如 午门→午门(入口)、北门→神武门(出口)、"
     "苏堤南段→苏堤；并剥离景点名尾部粘连的活动词（出发/出园/步行至/看日落等），"
     "解决“北宫门出园”“白堤步行至孤山”这类粘连问题。")

# 解析结果表
routes = json.load(open(os.path.join(OUT, "structured_routes.json"), encoding="utf-8"))
h("4.4 解析结果", 2)
for r in routes:
    para("【%s】声明格式=%s，识别格式=%s，共%d步" %
         (r["scenic"], r["expected_format"], r["detected_format"], len(r["steps"])), bold=True)
    add_table(["序号", "时段", "景点POI", "活动"],
              [[s["step_no"], s["time_period"], s["spot"], s["activity"]] for s in r["steps"]])

# ===== 5 时间维度层级 =====
h("五、时间维度层级结构构建", 1)
para("在原文中定位时段锚点（上午/中午/下午/傍晚）的字符位置，把有序景点按位置归入对应时段。"
     "针对“先列景点、句尾才说明时间安排”的箭头链路/编号列表，采用比例分配策略："
     "按时段数量把有序景点切分到上午/中午/下午，使层级结构与文本时间叙述一致。")
hier = json.load(open(os.path.join(OUT, "time_hierarchy.json"), encoding="utf-8"))
for hh in hier:
    para("【%s】" % hh["scenic"], bold=True)
    for pb in hh["periods"]:
        para("  [%s] %d站：%s" % (pb["period"], len(pb["steps"]),
             " → ".join(s["spot"] for s in pb["steps"])))
if os.path.exists(os.path.join(FIG, "time_hierarchy.png")):
    doc.add_picture(os.path.join(FIG, "time_hierarchy.png"), width=Inches(6.2))
    doc.add_paragraph("图1 三个景区的游览时间层级结构").alignment = WD_ALIGN_PARAGRAPH.CENTER

# ===== 6 官方 vs 游客对比 =====
h("六、官方路线与游客实际路线对比", 1)
para("以故宫为例，从一篇带爸妈游览的游记文本中按出现顺序抽取游客实际POI序列，与官方路线对比。")
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
        ["时间分配(上/中/下)", "官方%s vs 游客%s" % (cmp["time_allocation"]["official_am_noon_pm"], cmp["time_allocation"]["tourist_am_noon_pm"]), "中午时段游客少停一站"],
    ],
)
if os.path.exists(os.path.join(FIG, "route_compare.png")):
    doc.add_picture(os.path.join(FIG, "route_compare.png"), width=Inches(6.0))
    doc.add_paragraph("图2 官方路线与游客实际路线对比").alignment = WD_ALIGN_PARAGRAPH.CENTER

h("6.1 差异原因分析", 2)
para("(1) 覆盖度：游客带爸妈出行，在交泰殿这类“人多、无特别看点”的小殿直接穿过，未停留，"
     "故遗漏1个景点；官方路线追求覆盖完整而游客更重体验。")
para("(2) 顺序一致性：游客严格沿中轴线自午门至神武门单向游览，顺序与官方完全一致(LCS=100%)，"
     "说明官方路线的动线设计符合游客实际习惯。")
para("(3) 时间分配：游客中午在冰窖餐厅用餐休息，压缩了中午段停留景点数([3,2,3])，"
     "并在御花园（下午）因拍照停留更久——体现出“停留时长”上官方与游客的差异，"
     "官方按站点均分，游客按兴趣和体力弹性分配。")

# ===== 7 名称归一化与稳健性 =====
h("七、名称归一化、噪声处理与稳健性", 1)
para("· 简称/全称：午门=南门=入口，北门=神武门=出口，已统一映射；")
para("· 粘连处理：剥离“出发/出园/步行至/看日落”等尾部动词；")
para("· 过对齐风险：映射表仅覆盖已知景点，未命中词保留原文，避免误合并；")
para("· 局限：纯规则解析对自由句式（如“先逛了太和殿，又绕去御花园”）的鲁棒性有限，"
     "时间比例分配是启发式近似，后续可结合LLM做语义解析。")

# ===== 8 可复现性 =====
h("八、可复现性说明", 1)
para("运行：pip install -r requirements.txt 后执行 python run.py。")
para("输入：data/processed/scenic_dataset.json（统一数据集）。")
para("输出：output/structured_routes.json（结构化步骤）、time_hierarchy.json（时间层级）、"
     "route_compare.json（对比指标）；figures/ 下两张可视化图。")
para("关键中间结果：crawler/scenic_crawler.py 输出 data/raw/crawled_pages.json；"
     "load_industrycorpus.py 输出 data/processed/industrycorpus_tourism_sample.json。")

doc.save(os.path.join(ROOT, "实验三_游览路线层级结构挖掘_报告.docx"))
print("报告已生成:", os.path.join(ROOT, "实验三_游览路线层级结构挖掘_报告.docx"))
