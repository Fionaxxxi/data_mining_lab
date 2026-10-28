# 数据挖掘课程实验

仓库：[Fionaxxxi/data_mining_lab](https://github.com/Fionaxxxi/data_mining_lab)。正式代码按实验编号分目录，报告采用Markdown。

## 从这里开始

| 实验 | 代码目录 | 报告 | 结果位置 | 一键运行 |
|---|---|---|---|---|
| 一：数据采集与预处理 | [src/lab1/](src/lab1/) | [实验一报告.md](实验一报告.md) | `outputs/cleaned_data.*`及质量检查文件 | `.\run.ps1 -Lab 1` |
| 二：实体识别 | [src/lab2/](src/lab2/) | [实验二报告.md](实验二报告.md) | `outputs/lab2/` | `.\run.ps1 -Lab 2` |

`run.ps1 -Lab all`按一、二顺序执行。实验一默认使用已保存原文离线清洗，不重新爬取网站；实验二运行后自动检查实体位置和代表性案例。

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
| `archive/lab1/` | 旧Word生成代码、模板、草稿、截图和旧压缩包 | 历史归档，不参与正常实验运行 |

## 环境与运行

本项目统一使用`D:\miniconda3\envs\dm_scenic_lab`，不要使用base或其他项目的环境。实验二只用Python标准库，也使用同一个项目Conda环境。

```powershell
Set-Location D:\data_lab\scenic_lab1
.\run.ps1 -Lab 1
.\run.ps1 -Lab 2
```

环境尚不存在时：

```powershell
& D:\miniconda3\Scripts\conda.exe create --prefix D:\miniconda3\envs\dm_scenic_lab python=3.11 pip -y
& D:\miniconda3\envs\dm_scenic_lab\python.exe -m pip install -r requirements.txt
```

需要完整重走实验一的采集和材料准备时，依次执行：

```powershell
$py = 'D:\miniconda3\envs\dm_scenic_lab\python.exe'
& $py src\lab1\crawl_official.py
& $py src\lab1\prepare_data.py
.\run.ps1 -Lab 1
```

爬虫支持`--offline`：只解析现有快照，不发起请求，也不计为一次新的成功下载。在线请求记录在`data/source/crawl_manifest.json`，离线日志单独保存。

## 数据与实验衔接

| 目录或文件 | 内容 |
|---|---|
| `data/source/` | 两个原始Parquet分片、三个官方页面HTML及来源/采集记录 |
| `data/raw/selected_raw.jsonl` | 实验一选中的18份原始材料 |
| `outputs/cleaned_data.jsonl` | 实验一清洗结果，也是实验二及后续实验的统一文本输入 |
| `outputs/quality_report.json` | 实验一数据数量、缺失、重复、格式及幂等检查 |
| `outputs/cleaning_audit.csv` | 实验一逐条清洗审计 |
| `outputs/lab2/entities.json`、`entities.csv` | 实验二实体、规范名、来源和字符位置 |
| `outputs/lab2/stats.json`、`iteration.json`、`frequency_*.svg` | 实验二统计、规则迭代和三类词频图 |

数据路径保持稳定；代码目录调整不改变清洗文本及实体位置。大分片和候选JSONL通过Git LFS保存，克隆后执行`git lfs pull`获取完整数据。

数据来自[BAAI/IndustryCorpus2](https://modelscope.cn/datasets/BAAI/IndustryCorpus2)旅游地理中文分片，以及黄山、九寨沟官网和武陵源官方机构署名发布的路线。15篇游记缺少原网页URL，保留原记录ID、分片和行号，不编造来源；历史票价、开放状态和不当行为描述不能直接用作当前旅游建议。

`archive/lab1/`中的材料保留了早期文件及旧统计；查看正式实验内容请使用根目录两份Markdown报告和`outputs/`。以后新增实验按`src/lab3/`、`src/lab4/`等编号继续组织。
