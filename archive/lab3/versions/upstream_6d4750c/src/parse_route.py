# -*- coding: utf-8 -*-
"""
parse_route.py
==============
实验三核心：官方推荐路线的结构化解析（黄山 / 九寨沟 / 张家界）。

能力
----
1) 自动识别路线描述格式：arrow_chain(→) / numbered(1.) / time_segmented(上午…中午…下午…)
2) 把每条路线解析成统一结构步骤：step_no / time_period / spot(景点POI) / activity / raw_segment
3) 时间维度标注：按上午/中午/下午锚点归入时段
4) 名称归一化：简称/俗称/子景点映射到规范名

输出：output/structured_routes.json
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

# 名称归一化：别名/全称 -> 规范名（覆盖三景区）
NAME_NORMALIZE = {
    # 黄山
    "黄山南大门": "南大门(入口)", "云谷寺景观区": "云谷寺", "云谷寺": "云谷寺",
    "始信峰景观区": "始信峰", "始信峰": "始信峰",
    "狮子峰景观区": "狮子峰", "狮子峰": "狮子峰", "清凉台": "清凉台", "散花坞": "散花坞",
    "排云亭景观区": "排云亭", "排云亭": "排云亭",
    "天海景观区": "天海", "天海": "天海", "鳌鱼峰": "鳌鱼峰",
    "玉屏楼景观区": "玉屏楼", "玉屏楼": "玉屏楼", "迎客松": "迎客松",
    "慈光阁景观区": "慈光阁", "慈光阁": "慈光阁", "光明顶": "光明顶", "北海中路": "北海",
    "云谷索道": "云谷寺索道(交通)", "云谷": "云谷寺",
    "玉屏索道": "玉屏索道(交通)", "玉屏": "玉屏楼",
    "太平索道": "太平索道(交通)",
    # 九寨沟
    "沟口": "沟口", "树正群海": "树正群海", "老虎海": "老虎海", "犀牛海": "犀牛海",
    "诺日朗瀑布": "诺日朗瀑布", "五花海": "五花海", "珍珠滩瀑布": "珍珠滩瀑布",
    "镜海": "镜海", "长海": "长海", "五彩池": "五彩池",
    # 张家界
    "森林公园门票站": "森林公园门票站(入口)", "金鞭溪": "金鞭溪", "百龙天梯": "百龙天梯",
    "袁家界": "袁家界", "哈利路亚山": "乾坤柱(哈利路亚山)", "乾坤柱": "乾坤柱(哈利路亚山)",
    "天子山": "天子山", "贺龙公园": "贺龙公园", "御笔峰": "御笔峰",
    "天子山索道": "天子山索道(交通)",
    "武陵源门票站": "武陵源门票站(出口)", "出沟": "沟口(出口)", "进山": "门票站(入口)",
}

TIME_ANCHORS = ["早上", "上午", "中午", "下午", "傍晚", "晚上"]
TIME_NORMALIZE = {"早上": "上午", "上午": "上午", "中午": "中午",
                 "下午": "下午", "傍晚": "下午", "晚上": "晚上"}

ACTIVITY_VERBS = ["参观", "游览", "登", "乘", "乘索道", "观", "步行", "用餐",
                  "休息", "看日落", "看", "至", "出山", "出沟", "下山", "上山", "入"]

TRAILING_VERBS = ["景观区", "步行至", "看日落", "出发",
                  "出山", "出沟", "下山", "上山", "入", "用餐", "休息"]
TRAILING_SEG = ["进山", "上袁家界", "索道下行", "索道上行", "索道"]


def clean_spot(raw):
    raw = raw.strip(" ，。；;、→->()（）：:")
    changed = True
    while changed:
        changed = False
        for v in TRAILING_SEG:
            if raw.endswith(v) and len(raw) > len(v) + 1:
                raw = raw[: -len(v)]
                changed = True
        for v in TRAILING_VERBS:
            if raw.endswith(v) and len(raw) > len(v) + 1:
                raw = raw[: -len(v)]
                changed = True
    return NAME_NORMALIZE.get(raw.strip(), raw.strip())


def normalize_name(raw):
    return clean_spot(raw)


def detect_format(text):
    if re.search(r"\d+\s*[.、]\s*\S", text):
        return "numbered"
    if "→" in text or "->" in text:
        return "arrow_chain"
    if any(a in text for a in ["上午", "中午", "下午"]):
        return "time_segmented"
    return "unknown"


def time_period_map(text):
    m = {}
    for a in TIME_ANCHORS:
        for mm in re.finditer(a, text):
            m[mm.start()] = TIME_NORMALIZE[a]
    return m


def period_by_pos(pos, anchors, default="上午"):
    cur = default
    for p, period in sorted(anchors.items()):
        if pos >= p:
            cur = period
        else:
            break
    return cur


def extract_activity(seg):
    for v in ACTIVITY_VERBS:
        if v in seg:
            return v
    return "参观"


def parse_arrow_chain(text):
    parts = re.split(r"→|->", text)
    steps = []
    anchors = time_period_map(text)
    pos = 0
    for p in parts:
        if not p:
            continue
        seg = re.split(r"[。；;]", p)[0]
        seg = re.split(r"[：:]", seg)[-1]
        seg = seg.strip(" ，、")
        pos += len(seg) + 1
        # 先提取括号内并列景点，再处理主名
        seg_norm = seg.replace("（", "(").replace("）", ")")
        core, bracketed = seg_norm, []
        m = re.search(r"([\u4e00-\u9fa5A-Za-z]{2,10}?)\(([\u4e00-\u9fa5、]+)\)", seg_norm)
        if m:
            core = m.group(1)
            bracketed = [b for b in re.split(r"[、]", m.group(2))]
        for sp in [core] + bracketed:
            spot = normalize_name(sp)
            if not spot or len(spot) > 12:
                continue
            steps.append({"step_no": len(steps) + 1,
                          "time_period": period_by_pos(pos, anchors),
                          "spot": spot, "activity": extract_activity(seg),
                          "raw_segment": seg})
    return steps


def parse_numbered(text):
    items = re.findall(r"(\d+)\s*[.、]\s*([^；;。]+)", text)
    anchors = time_period_map(text)
    steps = []
    for no, seg in items:
        seg = seg.strip(" ，。；;、")
        spot = normalize_name(re.split(r"[（(]", seg)[0])
        steps.append({"step_no": int(no),
                      "time_period": period_by_pos(text.find(no + "."), anchors),
                      "spot": spot, "activity": extract_activity(seg),
                      "raw_segment": seg})
    return steps


def parse_time_segmented(text):
    pattern = "(" + "|".join(TIME_ANCHORS) + ")"
    chunks = re.split(pattern, text)
    steps = []
    cur_period = "上午"
    for i, chunk in enumerate(chunks):
        if chunk in TIME_ANCHORS:
            cur_period = TIME_NORMALIZE[chunk]
            continue
        if i == 0:
            continue
        spots_raw = re.findall(r"(?:从|经|至|走|登|乘|游|到)([\u4e00-\u9fa5]{2,10}?)(?=[，。；;、,])", chunk)
        spots = []
        for sr in spots_raw:
            for sub in re.split(r"步行至|至", sr):
                sub = clean_spot(sub)
                if sub:
                    spots.append(sub)
        for s in spots:
            steps.append({"step_no": len(steps) + 1,
                          "time_period": cur_period, "spot": s,
                          "activity": extract_activity(chunk),
                          "raw_segment": chunk[:30]})
    return steps


def parse_route(text, fmt=None):
    fmt = fmt or detect_format(text)
    if fmt == "arrow_chain":
        steps = parse_arrow_chain(text)
    elif fmt == "numbered":
        steps = parse_numbered(text)
    elif fmt == "time_segmented":
        steps = parse_time_segmented(text)
    else:
        steps = []
    return {"format": fmt, "steps": steps}


def dedupe_adjacent(steps):
    """去掉相邻重复景点（如 天子山 连续出现两次只留一个），并重排 step_no。"""
    out = []
    for s in steps:
        if out and out[-1]["spot"] == s["spot"]:
            continue
        s = dict(s); s["step_no"] = len(out) + 1
        out.append(s)
    return out


def main():
    ds = json.load(open(os.path.join(PROC, "scenic_dataset.json"), encoding="utf-8"))
    out = []
    for r in ds["official_routes"]:
        parsed = parse_route(r["text"])
        parsed["steps"] = dedupe_adjacent(parsed["steps"])
        out.append({"scenic": r["scenic"], "source": r["source"], "url": r["url"],
                    "text": r["text"], "detected_format": parsed["format"],
                    "expected_format": r["format"], "steps": parsed["steps"]})
        print("=" * 60)
        print("[%s] 声明格式=%s, 识别格式=%s, 步骤数=%d"
              % (r["scenic"], r["format"], parsed["format"], len(parsed["steps"])))
        for s in parsed["steps"]:
            print("   %2d [%s] %s  <%s>" % (s["step_no"], s["time_period"], s["spot"], s["activity"]))
    p = os.path.join(OUT, "structured_routes.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[parse_route] 输出 ->", p)


if __name__ == "__main__":
    main()
