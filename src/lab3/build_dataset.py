# -*- coding: utf-8 -*-
"""
build_dataset.py
================
汇总 黄山 / 九寨沟 / 张家界 三景区实验三统一数据集。

数据来源标注（可复现 / 可核查）：
- 爬虫采集    : crawler/scenic_crawler.py -> data/lab3/raw/crawled_pages.json
                （九寨沟官网 jiuzhai.com、张家界市政府 zjj.gov.cn、红网张家界 zjj.rednet.cn）
- 教师数据集  : src/load_industrycorpus.py -> IndustryCorpus2(BAAI) 住宿餐饮酒店中文语料
- 官方路线样本 : 黄山取自黄山风景区管委会官网“黄山一日游”线路；
                九寨沟、张家界依据官方/权威导览信息整理，覆盖箭头链路/编号列表/时间分段三种格式。
"""
import os, json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROC = os.path.join(ROOT, "data", "lab3", "processed")
RAW = os.path.join(ROOT, "data", "lab3", "raw")


def load_json(p, default):
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


# ---------- 官方推荐路线文本（三景区、三种格式） ----------
OFFICIAL_ROUTES = [
    {
        "scenic": "黄山",
        "format": "arrow_chain",
        "source": "黄山风景区管理委员会官网《黄山一日游》线路一",
        "url": "https://hsgwh.huangshan.gov.cn/lyfw/xltj/9135988.html",
        "text": ("黄山经典一日游推荐路线：黄山南大门 → 云谷寺景观区 →（云谷索道上行）→ "
                 "始信峰景观区 → 狮子峰景观区（清凉台、散花坞）→ 排云亭景观区 → "
                 "天海景观区（鳌鱼峰）→ 玉屏楼景观区（迎客松）→（玉屏索道下行）→ "
                 "慈光阁景观区 → 黄山南大门。全程约7小时，建议上午从云谷寺索道上山，"
                 "中午在北海景区或天海用餐，下午经排云亭、光明顶、迎客松下到玉屏索道下山。"),
    },
    {
        "scenic": "九寨沟",
        "format": "numbered",
        "source": "依据九寨沟景区官方导览整理",
        "url": "https://www.jiuzhai.com/",
        "text": ("九寨沟一日游推荐路线（日则沟+树正沟）：1.沟口；2.树正群海；3.老虎海；"
                 "4.犀牛海；5.诺日朗瀑布；6.五花海；7.珍珠滩瀑布；8.镜海；9.长海；"
                 "10.五彩池；11.出沟。建议上午先乘观光车到日则沟最高处五花海，沿栈道下行；"
                 "中午在诺日朗游客服务中心用餐；下午游树正沟与长海，傍晚出沟。"),
    },
    {
        "scenic": "张家界",
        "format": "time_segmented",
        "source": "依据张家界武陵源景区官方导览整理",
        "url": "https://www.zjj.gov.cn/",
        "text": ("张家界武陵源一日游：上午从森林公园门票站进山，游金鞭溪，乘百龙天梯上袁家界，"
                 "看哈利路亚山（乾坤柱）；中午在袁家界山顶用餐休息；下午游天子山、贺龙公园与御笔峰，"
                 "乘天子山索道下山，傍晚从武陵源门票站出山。"),
    },
]


def main():
    crawled = load_json(os.path.join(RAW, "crawled_pages.json"), [])
    ic = load_json(os.path.join(PROC, "industrycorpus_tourism_sample.json"), [])

    # 爬虫抓到的官方事实（九寨沟、张家界）
    official_facts = []
    for c in crawled:
        if c.get("ok") and c.get("tourism_para_count", 0) > 0:
            official_facts.append({
                "scenic": c.get("scenic"),
                "url": c.get("url"),
                "text": c.get("content", "")[:600],
            })

    # 游记语料：优先 IndustryCorpus2 中含 黄山/九寨沟/张家界 的片段
    travel_notes = []
    target_kw = ["黄山", "九寨沟", "张家界"]
    for s in ic:
        txt = s.get("content", "")
        if len(txt) < 120:
            continue
        scenic = next((k for k in target_kw if k in txt), "综合")
        travel_notes.append({
            "scenic": scenic,
            "source": s.get("source", "IndustryCorpus2"),
            "file": s.get("file", ""),
            "text_type": "游客/行业游览叙述语料",
            "text": txt,
        })
        if len(travel_notes) >= 12:
            break

    dataset = {
        "meta": {
            "description": "实验三 游览路线层级结构挖掘 统一数据集（黄山/九寨沟/张家界）",
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
