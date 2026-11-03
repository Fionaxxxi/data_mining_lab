# -*- coding: utf-8 -*-
"""
compare_routes.py
=================
实验三高阶任务：对比“官方推荐路线”与“游客游记中隐含的实际路线”的层级差异。

方法
----
1) 从一篇故宫游记文本中，用景点名词典按出现顺序抽取游客实际游览的 POI 序列；
2) 与官方结构化路线（output/structured_routes.json）对比，计算：
   - 景点覆盖度：游客实际走到的官方景点占比；
   - 顺序一致性：用最长公共子序列(LCS)衡量两条路线的顺序吻合度；
   - 时间分配：上午/中午/下午各自停留的景点数对比；
3) 输出对比 JSON 与对比柱状图 figures/route_compare.png。
"""
import os, re, json
from difflib import SequenceMatcher
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
FIG = os.path.join(ROOT, "figures")

for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"] = False

# 景点名 -> 规范名（与 parse_route 保持一致）
NAME2NORM = {
    "午门": "午门(入口)", "太和殿": "太和殿", "中和殿": "中和殿", "保和殿": "保和殿",
    "乾清宫": "乾清宫", "交泰殿": "交泰殿", "坤宁宫": "坤宁宫", "御花园": "御花园",
    "神武门": "神武门(出口)",
}

# 一篇代表性故宫游客游记（隐含实际路线）
TOURIST_NOTE = (
    "周末带爸妈逛故宫，早上八点半从午门刷身份证进宫。先在太和殿广场拍了全家福，"
    "中和殿很小就路过看了一眼，保和殿也走马观花。走到乾清宫人挤人，拍了张照，"
    "中间那座小殿人太多基本没停留直接走了，坤宁宫进去转了一圈。中午在冰窖餐厅吃饭休息。"
    "下午在御花园待得最久，爸妈很喜欢假山花木拍了很多照片，最后慢悠悠从神武门出来。"
)


def extract_poi_sequence(text):
    """按出现位置抽取命中词典的景点规范名序列（保序去重）。"""
    hits = []
    for raw, norm in NAME2NORM.items():
        for m in re.finditer(raw, text):
            hits.append((m.start(), norm))
    hits.sort()
    seq, seen = [], set()
    for _, norm in hits:
        if norm not in seen:
            seen.add(norm); seq.append(norm)
    return seq


def lcs_length(a, b):
    sm = SequenceMatcher(a=list(a), b=list(b))
    return sum(block.size for block in sm.get_matching_blocks())


def main():
    routes = json.load(open(os.path.join(OUT, "structured_routes.json"), encoding="utf-8"))
    official = next(r for r in routes if r["scenic"] == "故宫")
    official_seq = [s["spot"] for s in official["steps"]]

    tourist_seq = extract_poi_sequence(TOURIST_NOTE)

    off_set, tou_set = set(official_seq), set(tourist_seq)
    coverage = len(off_set & tou_set) / len(off_set)
    lcs = lcs_length(official_seq, tourist_seq)
    order_consistency = lcs / min(len(official_seq), len(tourist_seq))

    # 时间分配（按序列位置均分三段做近似）
    def period_counts(seq):
        n = len(seq); k = 3
        bounds = [round(i * n / k) for i in range(k + 1)]
        return [bounds[i+1]-bounds[i] for i in range(k)]
    off_counts = period_counts(official_seq)
    tou_counts = period_counts(tourist_seq)

    result = {
        "scenic": "故宫",
        "official_seq": official_seq,
        "tourist_seq": tourist_seq,
        "metrics": {
            "coverage": round(coverage, 3),
            "order_consistency": round(order_consistency, 3),
            "official_len": len(official_seq),
            "tourist_len": len(tourist_seq),
            "missing_in_tourist": sorted(off_set - tou_set),
        },
        "time_allocation": {"official_am_noon_pm": off_counts, "tourist_am_noon_pm": tou_counts},
        "tourist_note": TOURIST_NOTE,
    }
    p = os.path.join(OUT, "route_compare.json")
    json.dump(result, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("官方路线(%d站):" % len(official_seq), " -> ".join(official_seq))
    print("游客路线(%d站):" % len(tourist_seq), " -> ".join(tourist_seq))
    print("景点覆盖度 = %.1f%%" % (coverage*100))
    print("顺序一致性(LCS) = %.1f%%" % (order_consistency*100))
    print("游客遗漏景点:", sorted(off_set - tou_set))
    print("时间分配 官方(上/中/下):", off_counts, " 游客:", tou_counts)

    # 对比柱状图
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    periods = ["上午", "中午", "下午"]
    x = range(3); w = 0.35
    axes[0].bar([i-w/2 for i in x], off_counts, w, label="官方路线", color="#4C72B0")
    axes[0].bar([i+w/2 for i in x], tou_counts, w, label="游客实际", color="#DD8452")
    axes[0].set_xticks(list(x)); axes[0].set_xticklabels(periods)
    axes[0].set_ylabel("游览景点数"); axes[0].set_title("官方 vs 游客：时间分配对比")
    axes[0].legend()
    axes[1].bar(["景点覆盖度", "顺序一致性"], [coverage*100, order_consistency*100],
                color=["#55A868", "#C44E52"])
    axes[1].set_ylim(0, 105); axes[1].set_ylabel("百分比 %")
    axes[1].set_title("官方-游客路线结构相似度")
    for i, v in enumerate([coverage*100, order_consistency*100]):
        axes[1].text(i, v+2, "%.0f%%" % v, ha="center")
    plt.tight_layout()
    figp = os.path.join(FIG, "route_compare.png")
    plt.savefig(figp, dpi=150, bbox_inches="tight"); plt.close()
    print("[compare] 输出 %s 和 %s" % (p, figp))


if __name__ == "__main__":
    main()
