# -*- coding: utf-8 -*-
"""
build_dataset.py
================
把两路采集结果 + 整理自官方导览的路线样本，汇总成实验三统一使用的数据集
data/processed/scenic_dataset.json。

数据来源标注（可复现 / 可核查）：
- crawler 采集  : crawler/scenic_crawler.py  -> data/raw/crawled_pages.json
                  实际抓取 故宫博物院官网(dpm.org.cn) 等真实页面。
- 教师数据集    : src/load_industrycorpus.py -> IndustryCorpus2(BAAI) 住宿餐饮酒店中文语料。
- 官方路线样本   : 依据官网导览信息整理的代表性路线文本（覆盖箭头链路/编号列表/时间分段
                  三种描述格式），URL 指向对应官网导览入口。
"""
import os, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
RAW = os.path.join(ROOT, "data", "raw")


def load_json(p, default):
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


# ---------- 官方推荐路线文本（多格式样本） ----------
# format: arrow_chain 箭头链路 / numbered 编号列表 / time_segmented 时间分段
OFFICIAL_ROUTES = [
    {
        "scenic": "故宫",
        "format": "arrow_chain",
        "source": "整理自故宫博物院官网导览(dpm.org.cn，爬虫已抓取首页开放信息)",
        "url": "https://www.dpm.org.cn/Home.html",
        "text": ("故宫中轴线一日游推荐路线：午门 → 太和殿 → 中和殿 → 保和殿 → "
                 "乾清宫 → 交泰殿 → 坤宁宫 → 御花园 → 神武门。"
                 "全程步行约3小时。建议上午08:30从午门入宫，先沿中轴线参观外朝前三殿；"
                 "中午在乾清宫广场附近休息；下午参观内廷后三宫与御花园，16:00前由神武门出宫。"),
    },
    {
        "scenic": "颐和园",
        "format": "numbered",
        "source": "整理自颐和园官网导览",
        "url": "https://www.summerpalace-china.com/",
        "text": ("颐和园东宫门入园一日游路线：1.仁寿殿；2.玉澜堂；3.乐寿堂；"
                 "4.长廊(邀月门→排云门)；5.排云殿；6.佛香阁；7.苏州街；8.北宫门出园。"
                 "建议上午先登万寿山，中午在长廊附近用餐，下午沿昆明湖畔漫步至十七孔桥。"),
    },
    {
        "scenic": "西湖",
        "format": "time_segmented",
        "source": "整理自杭州西湖风景名胜区官方导览",
        "url": "https://westlake.hangzhou.gov.cn/",
        "text": ("西湖经典环湖一日游：上午从断桥出发，经白堤步行至孤山；"
                 "中午在楼外楼用餐；下午游曲院风荷，乘船横渡西湖至三潭印月，"
                 "上岸后走苏堤南段；傍晚到花港观鱼，登雷峰塔看日落。"),
    },
]


def main():
    crawled = load_json(os.path.join(RAW, "crawled_pages.json"), [])
    ic = load_json(os.path.join(PROC, "industrycorpus_tourism_sample.json"), [])

    # 从爬虫结果里取故宫官网的真实官方信息（开放时间等）作为官方事实补充
    official_facts = []
    for c in crawled:
        if c.get("ok") and c.get("tourism_para_count", 0) > 0:
            official_facts.append({
                "scenic": c.get("scenic"),
                "url": c.get("url"),
                "text": c.get("content", "")[:600],
            })

    # 游记：优先用 IndustryCorpus2 中与景区游览相关的若干条
    travel_notes = []
    for s in ic:
        txt = s.get("content", "")
        if len(txt) < 120:
            continue
        travel_notes.append({
            "scenic": "综合",
            "source": s.get("source", "IndustryCorpus2"),
            "file": s.get("file", ""),
            "text_type": "游客/行业游览叙述语料",
            "text": txt,
        })
        if len(travel_notes) >= 12:
            break

    dataset = {
        "meta": {
            "description": "实验三 游览路线层级结构挖掘 统一数据集",
            "official_facts_from_crawler": official_facts,
        },
        "official_routes": OFFICIAL_ROUTES,
        "travel_notes": travel_notes,
    }
    out = os.path.join(PROC, "scenic_dataset.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print("[build_dataset] 官方路线 %d 条, 游记语料 %d 条, 官网事实 %d 条 -> %s"
          % (len(OFFICIAL_ROUTES), len(travel_notes), len(official_facts), out))


if __name__ == "__main__":
    main()
