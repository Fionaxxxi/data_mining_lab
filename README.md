# 数据挖掘课程实验

仓库：[Fionaxxxi/data_mining_lab](https://github.com/Fionaxxxi/data_mining_lab)。正式代码按实验编号分目录，报告采用Markdown。

## 从这里开始

| 实验 | 代码目录 | 报告 | 结果位置 | 一键运行 |
|---|---|---|---|---|
| 一：数据采集与预处理 | [src/lab1/](src/lab1/) | [实验一报告.md](实验一报告.md) | `outputs/cleaned_data.*`及质量检查文件 | `.\run.ps1 -Lab 1` |
| 二：实体识别 | [src/lab2/](src/lab2/) | [实验二报告.md](实验二报告.md) | `outputs/lab2/` | `.\run.ps1 -Lab 2` |
| 三：游览路线层级结构 | [src/lab3/](src/lab3/) | [实验三报告.md](实验三报告.md) | `outputs/lab3/` | `.\run.ps1 -Lab 3` |
| 四：共指消解 | [src/lab4/](src/lab4/) | [实验四报告.md](实验四报告.md) | `outputs/lab4/` | `.\run.ps1 -Lab 4` |
| 五：条件性游览建议抽取 | [src/lab5/](src/lab5/) | [实验五报告.md](实验五报告.md) | `outputs/lab5/` | `.\run.ps1 -Lab 5` |
| 六：多源知识融合与图谱 | [src/lab6/](src/lab6/) | [实验六报告.md](实验六报告.md) | `outputs/lab6/` | `.\run.ps1 -Lab 6` |
| 七：旅游规划 Agent | [实验七/](实验七/) | [实验七报告](实验七/实验七报告.md) | `实验七/outputs/lab7/` | `.\run.ps1 -Lab 7` |

`run.ps1 -Lab all`按一至七顺序执行。实验三使用 `data/lab3/` 中已有样本离线运行，不自动联网采集或生成 Word。实验一默认使用已保存原文离线清洗，不重新爬取网站；实验二运行后自动检查实体位置和代表性案例。实验七的代码、专用输入、结果、报告和计划集中在 `实验七/`。

## 每个脚本负责什么

| 位置 | 职责 | 何时使用 |
|---|---|---|
| `src/lab1/crawl_official.py` | 请求官方路线页面，解析正文，保存HTML及真实采集记录 | 需要重新采集官网路线时 |
| `src/lab1/prepare_data.py` | 从Parquet中提取15篇选定游记，合并3份官方路线 | 需要重建原始输入时 |
| `src/lab1/preprocess.py` | 批量清洗18份材料，导出CSV/JSONL及质量检查结果 | 实验一正式处理入口 |
| `src/lab1/tools/inspect_source.py` | 查看首个分片字段及候选材料 | 可选探索工具，日常复跑不需要 |
| `src/lab1/tools/scan_candidates.py` | 对两个分片进行候选初筛 | 可选探索工具，日常复跑不需要 |
| `src/lab2/entities.py` | 识别POI、交通、时间实体，保存位置、统计、迭代结果及词频图 | 实验二正式处理入口 |
| `src/lab2/check.py` | 检查实体与原文位置、来源覆盖及正反案例 | 实验二检查入口 |
| `src/lab3/` | 样本汇总、路线解析、时间层级及官方/游客路线对比；采集脚本手动调用 | 实验三正式入口 |
| `src/lab4/coref.py`、`figures.py` | 代词检测、消解、人工核验统计及配图 | 实验四入口 |
| `src/lab5/extract.py`、`finalize.py`、`figures.py` | 条件建议候选、审阅映射、分类统计及柱状图 | 实验五入口 |
| `实验七/` | 旅游规划 Agent 的代码、输入、实验六最小复用数据、结果与文档 | 实验七入口与完整材料 |

## 环境与运行

当前运行入口使用本项目的 Python 3.11 Conda 环境 `D:\miniconda3\envs\dm_scenic_lab`。实验四、五的正式脚本只使用标准库。

```powershell
Set-Location 'D:\data_lab\scenic_lab1'
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Lab 5
```

环境尚不存在时（已存在则使用 `conda env update -f environment.yml`）：

```powershell
& D:\miniconda3\Scripts\conda.exe env create -f environment.yml
```

需要完整重走实验一的采集和材料准备时，依次执行：

```powershell
$py = 'D:\miniconda3\envs\dm_scenic_lab\python.exe'
& $py src\lab1\crawl_official.py
& $py src\lab1\prepare_data.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Lab 1
```

爬虫支持`--offline`：只解析现有快照，不发起请求，也不计为一次新的成功下载。在线请求记录在`data/source/crawl_manifest.json`，离线日志单独保存。

## 数据与实验衔接

| 目录或文件 | 内容 |
|---|---|
| `data/lab3/raw/`、`data/lab3/processed/` | 实验三原始采集、抽样语料及统一路线数据集 |
| `outputs/lab3/` | 实验三结构化路线、时间层级、对比 JSON 和 figures 图表 |
| `docs/` | 每阶段唯一执行计划及实施验收报告 |
| `data/source/` | 两个原始Parquet分片、三个官方页面HTML及来源/采集记录 |
| `data/raw/selected_raw.jsonl` | 实验一选中的18份原始材料 |
| `outputs/cleaned_data.jsonl` | 实验一清洗结果，也是实验二及后续实验的统一文本输入 |
| `outputs/quality_report.json` | 实验一数据数量、缺失、重复、格式及幂等检查 |
| `outputs/cleaning_audit.csv` | 实验一逐条清洗审计 |
| `outputs/lab2/entities.json`、`entities.csv` | 实验二实体、规范名、来源和字符位置 |
| `outputs/lab2/stats.json`、`iteration.json`、`frequency_*.svg` | 实验二统计、规则迭代和三类词频图 |
| `outputs/lab5/mapping.json`、`mapping.csv`、`stats.json` | 实验五经逐条核对的条件—建议映射及分类统计；小组人工抽查见 `outputs/lab5/人工抽查记录.md` |

数据路径保持稳定；代码目录调整不改变清洗文本及实体位置。大分片和候选JSONL通过Git LFS保存，克隆后执行`git lfs pull`获取完整数据。

数据来自[BAAI/IndustryCorpus2](https://modelscope.cn/datasets/BAAI/IndustryCorpus2)旅游地理中文分片，以及黄山、九寨沟官网和武陵源官方机构署名发布的路线。15篇游记缺少原网页URL，保留原记录ID、分片和行号，不编造来源；历史票价、开放状态和不当行为描述不能直接用作当前旅游建议。

旧实验归档已按用户要求删除；正式实验内容以根目录报告、`src/` 和 `outputs/` 为准。以后新增实验按编号继续组织。

## 整理后的目录约定

```text
scenic_lab1/
├── src/lab1 … lab5/       # 正式代码，按实验编号
├── data/                 # 实验一既有输入保留；实验三独立输入在 lab3/
├── outputs/              # 实验一既有输出保留；lab2 … lab5/ 为各实验结果
├── docs/                 # 阶段计划与验收报告
├── 实验一报告.md … 实验五报告.md
├── run.ps1               # 统一入口
└── environment.yml、requirements.txt
```

本次整理详情见 [目录整理实施验收报告](docs/目录整理实施验收报告.md)。根目录已有任务书、实验一 Word 和 Office 临时锁文件暂保留原位，未修改其内容。


## 当前版本与实验六

实验三使用提交6d4750c的黄山/九寨沟/张家界版本，位于src/lab3、data/lab3、outputs/lab3。此前旧版实验三和实验六已按用户要求删除。

实验六入口 `powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Lab 6`，顺序完成构图、查询、可视化和验收。默认读取前序已保存成果，不会重跑或覆盖前序输入。输出结构在 `outputs/lab6/graph.json`、`graph.graphml`、`nodes.csv`、`edges.csv`；图在 `outputs/lab6/figures/`，查询在 `queries.json`，验收在 `acceptance.json`。

实验七的所有在用材料集中于 `实验七/`，复用的实验六最小图谱副本位于 `实验七/outputs/lab6/`。测试集和真实 LLM 在线场景测试方法见 [实验七测试集说明](实验七/测试集说明.md)。项目统一入口使用 `D:\miniconda3\envs\dm_scenic_lab`。

实验一当前JSONL的既有格式问题仍保留；实验六校验同阶段CSV正文哈希、原始文本与全部实体位置后读取CSV。`all`可能先重建实验一文件，日常复核实验六直接使用 `-Lab 6`。执行计划见docs/实验六执行计划.md，完整方法和局限见实验六报告.md。
