# 数据挖掘实验一

项目仓库：https://github.com/Fionaxxxi/data_mining_lab 。后续数据挖掘课程实验统一在本仓库继续。

**当前报告以根目录的[实验一报告.md](实验一报告.md)为准。** `report/`、`qa/`、评分核对文档及压缩包为此前草稿或验证记录，按“上传文件夹全部内容”的要求保留，其中部分旧统计未随最终Markdown更新。最新数据与统计以`outputs/`为准。原始Parquet和大候选集通过Git LFS保存，克隆后执行`git lfs pull`获取完整数据。

已完成黄山、九寨沟、张家界三个景区的数据准备、清洗、结构化与质量检查。最终18条记录，每个景区1份官方指南和5篇游客游记。官方指南可能包含多条路线，记录数按文档计算。

## 先看这些文件

- `report/探索性实验报告_已填实验一.docx`：在原报告模板副本中填写了1.1—1.5节。封面、小组贡献、教师评分、实验2—7及总结保持原模板内容，尚不是全课程最终报告。
- `report/实验一可粘贴内容.md`：对应章节的可复制文字。
- `outputs/cleaned_data.csv`、`outputs/cleaned_data.jsonl`：同一份18条规范数据，保留原文和清洗正文。
- `outputs/quality_report.json`、`cleaning_audit.csv`、`before_after_samples.json`：统计、逐条规则审计与对比。
- `outputs/source_index.csv`：来源、原记录ID、分片行号及官方URL。

## 环境与离线复现

本机环境：`D:\miniconda3\envs\dm_scenic_lab`，Python 3.11.18。不要使用base或其他项目环境。

```powershell
Set-Location D:\data_lab\scenic_lab1
& D:\miniconda3\envs\dm_scenic_lab\python.exe .\src\run_lab1.py
```

此命令只读取已保留的`data/raw/selected_raw.jsonl`，不联网、不需要下载完整数据集，会重新生成outputs中的清洗结果及统计。正文CSV采用UTF-8 BOM，内嵌换行符合CSV引号转义规则。若用Excel导入，请把source_record_id列指定为文本，避免长整数精度丢失。

另一台电脑可在自己的D盘Miniconda目录中新建本项目独立环境：

```powershell
& D:\miniconda3\Scripts\conda.exe create --prefix D:\miniconda3\envs\dm_scenic_lab python=3.11 pip -y
& D:\miniconda3\envs\dm_scenic_lab\python.exe -m pip install -r requirements.txt
& D:\miniconda3\envs\dm_scenic_lab\python.exe src\run_lab1.py
```

若本环境已经存在，跳过create，直接执行清洗入口。`requirements.txt`只列本项目实际脚本依赖；报告构建另外使用python-docx/lxml。下载与清洗不需要API密钥。

## 官网爬虫与材料准备

`src/crawl_official.py`使用Python标准库urllib.request和BeautifulSoup定向采集三个官方发布页面。运行命令为`& D:\miniconda3\envs\dm_scenic_lab\python.exe src\crawl_official.py`。程序设置25秒超时、每个URL最多两次尝试，支持同篇官方机构路线的备用发布地址，校验正文后才保存HTML；结果为`data/raw/official_routes.jsonl`，真实请求记录为`data/source/crawl_manifest.json`。黄山、九寨沟和张家界共3份路线均成功采集并保存HTML；张家界实际采集地址为武陵源新闻网的官方机构署名原发页面。实际URL、发布机构、请求时间和哈希均入库，失败尝试同样记录。`--offline`只解析已保存材料，其日志单独保存，不覆盖在线采集日志。

## 从完整分片重建选中原始材料

本机`data/source`已保存约597 MB的两个Parquet分片，SHA-256见manifest.json。提交精简包不重复打包大分片，但保留所有18条选中原文；需要独立验证抽样来源时，按`data/source/DOWNLOAD.md`下载两个精确文件并校验哈希，再执行：

```powershell
& D:\miniconda3\envs\dm_scenic_lab\python.exe src\crawl_official.py
& D:\miniconda3\envs\dm_scenic_lab\python.exe src\prepare_data.py
& D:\miniconda3\envs\dm_scenic_lab\python.exe src\run_lab1.py
```

prepare_data.py按已复核的记录位置精确提取，不随机抽样。全局筛选索引是两个分片连接后的索引，最终输出source_row_index是各自分片内从0计的行号。`scan_candidates.py`用于记录初筛过程，非自动判定游记真实性的分类器。源码中的候选检查脚本不是网站爬虫。

## 来源与限制

主数据源：https://modelscope.cn/datasets/BAAI/IndustryCorpus2 。使用旅游/地理中文high与middle各一个分片，不使用Hugging Face镜像替代数据源。

原语料只有text、_id、industry_type和质量指标，没有原网页URL。15篇游记的原URL如实留空，通过分片、行号和_id追溯；游记身份为内容判断，未认证原作者。以官方页面补充3份指南，混合来源已注明：

- 黄山：https://wap.huangshan.com.cn/detail/strategy/fjqlyzx ，第20问，保留HTML快照及原内容字段。
- 九寨沟：https://www.jiuzhai.com/intelligent-service/way-of-play ，一日精华游节选，保留HTML快照。
- 张家界：https://www.wlynews.cn/content/2021/09/18/10178438.html ，武陵源区委旅游工作委员会办公室署名发布的一日游路线，日期2021-09-18，保留完整HTML快照。省文旅厅同文页面为配置中的首选地址，连接失败时爬虫使用此原发页面。

数据整理日期2026-10-28。历史票价、逃票/翻越封闭设施/投喂野生动物等原文描述不是现行事实或推荐行为，不宜直接传入旅游Agent。九寨沟官方文末时间段存在重叠，原样保留并在报告分析。张家界游记中包括外围行程，下游须区分武陵源、天门山、凤凰古城等范围。

使用LLM辅助候选内容复核与报告整理；未声称学生已完成个人操作或人工标注。三人姓名、学号、贡献比例须按实际补填，不能直接把本报告当作全课程报告提交。

## 验证与文件对应

run_lab1.py实际验证：每景区1+5；关键字段无空白；SHA-256完全去重；同景区同类型SequenceMatcher近重复阈值0.80；残留HTML、U+FFFD、空白格式；清洗幂等；真实官方记录中的箭头和时间保留；CSV读回正文与JSONL一致。近重复算法只做提示，未计算语义重复。

报告数值来自quality_report.json；逐条改动见cleaning_audit.csv。未发生的规则命中没有伪造成真实清洗问题。数据中原文错误不自动改写，不能以形式检查通过代替内容事实核验。
