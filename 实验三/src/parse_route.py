# -*- coding: utf-8 -*-
"""
parse_route.py
==============
实验三核心：官方推荐路线的结构化解析。

能力
----
1) 自动识别路线描述格式：
   - arrow_chain    箭头链路：午门 -> 太和殿 -> 中和殿 ...
   - numbered       编号列表：1.仁寿殿；2.玉澜堂；...
   - time_segmented 时间分段：上午...中午...下午...
2) 把每条路线解析成统一结构的步骤列表，字段：
   step_no / time_period / spot(景点POI) / activity(活动) / raw_segment
3) 时间维度标注：根据“上午/中午/下午/傍晚”等锚点，把步骤归入时段。
4) 名称归一化：把简称/俗称/子景点映射到规范名，记录别名。

输出
----
output/structured_routes.json
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

# 名称归一化映射：别名/俗称/全称 -> 规范名
NAME_NORMALIZE = {
    "午门": "午门(入口)", "南门": "午门(入口)",
    "神武门": "神武门(出口)", "北门": "神武门(出口)",
    "太和殿": "太和殿", "中和殿": "中和殿", "保和殿": "保和殿",
    "乾清宫": "乾清宫", "交泰殿": "交泰殿", "坤宁宫": "坤宁宫",
    "御花园": "御花园",
    "仁寿殿": "仁寿殿", "玉澜堂": "玉澜堂", "乐寿堂": "乐寿堂",
    "长廊": "长廊", "排云殿": "排云殿", "佛香阁": "佛香阁",
    "苏州街": "苏州街", "东宫门": "东宫门(入口)", "北宫门": "北宫门(出口)",
    "十七孔桥": "十七孔桥", "昆明湖": "昆明湖", "万寿山": "万寿山",
    "断桥": "断桥", "白堤": "白堤", "孤山": "孤山", "浙江省博物馆": "浙江省博物馆",
    "曲院风荷": "曲院风荷", "三潭印月": "三潭印月", "苏堤": "苏堤",
    "苏堤南段": "苏堤", "花港观鱼": "花港观鱼", "雷峰塔": "雷峰塔", "楼外楼": "楼外楼(用餐点)",
}

TIME_ANCHORS = ["早上", "上午", "中午", "下午", "傍晚", "晚上"]
TIME_NORMALIZE = {"早上": "上午", "中午": "中午", "上午": "上午",
                 "下午": "下午", "傍晚": "下午", "晚上": "晚上"}

ACTIVITY_VERBS = ["参观", "游览", "登", "乘船", "漫步", "步行", "用餐",
                  "休息", "看日落", "看", "横渡", "至", "出园", "入宫", "出宫"]


# 景点名尾部粘连的活动词，需剥离
TRAILING_VERBS = ["步行至", "横渡", "看日落", "出发", "出园", "出宫", "入宫",
                  "步行", "漫步", "参观", "游览", "至", "登"]


def clean_spot(raw):
    """从粗糙片段中剥离活动动词，提取规范景点名。"""
    raw = raw.strip(" ，。；;、->→")
    changed = True
    while changed:
        changed = False
        for v in TRAILING_VERBS:
            if raw.endswith(v) and len(raw) > len(v) + 1:
                raw = raw[: -len(v)]
                changed = True
    return NAME_NORMALIZE.get(raw.strip(), raw.strip())


def normalize_name(raw):
    return clean_spot(raw)


def detect_format(text):
    # 编号列表优先级最高（括号内可能含箭头，避免误判为箭头链路）
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
        p = p.strip(" ，。；;、")
        if not p:
            continue
        # 先截取第一句（去掉句号后的说明），再去掉“推荐路线：”前缀
        seg = re.split(r"[。；;]", p)[0]
        seg = re.split(r"[：:]", seg)[-1]
        seg = seg.strip(" ，、")
        pos += len(seg) + 1
        spot = normalize_name(seg)
        if not spot or len(spot) > 12:
            continue
        steps.append({
            "step_no": len(steps) + 1,
            "time_period": period_by_pos(pos, anchors),
            "spot": spot,
            "activity": extract_activity(p),
            "raw_segment": p,
        })
    return steps


def parse_numbered(text):
    items = re.findall(r"(\d+)\s*[.、]\s*([^；;。]+)", text)
    anchors = time_period_map(text)
    steps = []
    for no, seg in items:
        seg = seg.strip(" ，。；;、")
        spot = normalize_name(re.split(r"[（(]", seg)[0])
        steps.append({
            "step_no": int(no),
            "time_period": period_by_pos(text.find(no + "."), anchors),
            "spot": spot,
            "activity": extract_activity(seg),
            "raw_segment": seg,
        })
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
        spots_raw = re.findall(r"(?:从|经|至|走|登|参观|游|乘船?横渡?)([\u4e00-\u9fa5]{2,10}?)(?=[，。；;、,])", chunk)
        spots = []
        for sr in spots_raw:
            # “白堤步行至孤山”这类再按“至”拆成多个景点
            for sub in re.split(r"步行至|至", sr):
                sub = clean_spot(sub)
                if sub:
                    spots.append(sub)
        for s in spots:
            steps.append({
                "step_no": len(steps) + 1,
                "time_period": cur_period,
                "spot": s,
                "activity": extract_activity(chunk),
                "raw_segment": chunk[:30],
            })
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


def main():
    ds = json.load(open(os.path.join(PROC, "scenic_dataset.json"), encoding="utf-8"))
    out = []
    for r in ds["official_routes"]:
        parsed = parse_route(r["text"])
        out.append({
            "scenic": r["scenic"],
            "source": r["source"],
            "url": r["url"],
            "text": r["text"],
            "detected_format": parsed["format"],
            "expected_format": r["format"],
            "steps": parsed["steps"],
        })
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
