# 实验三：游览路线的层级结构挖掘

《数据挖掘》探索性实验 · 实验项目3 —— 面向程序性文本的层级结构挖掘。

## 一、实验目标
1. 分析官方推荐路线的文本描述模式，设计解析规则，把每条路线转成统一的结构化表示（步骤/时间/景点/活动）；
2. 基于解析结果构建以时间（上午/中午/下午）为维度的游览层级结构；
3. 对比同一景区“官方推荐路线”与“游客游记隐含实际路线”的层级差异并分析原因。

## 二、数据来源（两路采集 + 整理样本）
| 来源 | 说明 | 脚本 |
|---|---|---|
| 爬虫采集 | requests+BeautifulSoup 实际抓取故宫博物院官网(dpm.org.cn)等真实页面 | `crawler/scenic_crawler.py` |
| 教师数据集 | modelscope `BAAI/IndustryCorpus2` 住宿餐饮酒店中文语料，按旅游关键词过滤抽样 | `src/load_industrycorpus.py` |
| 官方路线样本 | 依据官网导览信息整理，覆盖箭头链路/编号列表/时间分段三种格式 | `src/build_dataset.py` |

## 三、目录结构
```
实验三_游览路线层级结构挖掘/
├── run.py                     # 一键运行入口
├── requirements.txt
├── crawler/scenic_crawler.py  # 爬虫
├── src/
│   ├── load_industrycorpus.py  # 加载教师数据集
│   ├── build_dataset.py        # 汇总统一数据集
│   ├── parse_route.py         # 官方路线结构化解析(格式识别+名称归一化)
│   ├── time_hierarchy.py      # 时间维度层级构建
│   └── compare_routes.py       # 官方 vs 游客路线对比
├── data/raw/                  # 爬虫原始结果、数据集缓存
├── data/processed/             # 清洗后统一数据集
├── output/                     # structured_routes.json / time_hierarchy.json / route_compare.json
└── figures/                    # time_hierarchy.png / route_compare.png
```

## 四、运行方式
```bash
pip install -r requirements.txt
python run.py
```
或单步运行：`python src/parse_route.py` 等。

## 五、主要输出
- `output/structured_routes.json`：每条路线的步骤序列（step_no/time_period/spot/activity）；
- `output/time_hierarchy.json` + `figures/time_hierarchy.png`：上午/中午/下午层级结构；
- `output/route_compare.json` + `figures/route_compare.png`：官方-游客覆盖度/顺序一致性/时间分配对比。
