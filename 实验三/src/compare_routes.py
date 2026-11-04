# -*- coding: utf-8 -*-
"""
compare_routes.py
=================
实验三高阶任务：对比“官方推荐路线”与“游客游记中隐含的实际路线”的层级差异（以黄山为例）。

方法：
1) 从一篇黄山游客游记文本中，用景点名词典按出现顺序抽取游客实际游览的 POI 序列；
2) 与官方结构化路线对比，计算景点覆盖度、顺序一致性(LCS)、时间分配；
3) 输出对比 JSON 与柱状图。
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

# 黄山景点名 -> 规范名
NAME2NORM = {
    "南大门": "南大门(入口)", "云谷寺": "云谷寺", "始信峰": "始信峰",
    "狮子峰": "狮子峰", "清凉台": "清凉台", "散花坞": "散花坞",
    "排云亭": "排云亭", "天海": "天海", "鳌鱼峰": "鳌鱼峰",
    "玉屏楼": "玉屏楼", "迎客松": "迎客松", "慈光阁": "慈光阁",
    "光明顶": "光明顶",
}

# 一篇代表性黄山游客游记（隐含实际路线）
TOURIST_NOTE = (
    "凌晨四点半从南大门出发，赶第一班云谷索道上山，到了白鹅岭先看日出，"
    "然后去始信峰，沿途经过黑虎松、连理松，又到狮子峰看了清凉台和猴子观海。"
    "中午在北海宾馆吃饭休息了一会儿。下午翻过光明顶到天海，经鳌鱼峰走百步云梯，"
    "到玉屏楼看了迎客松，最后坐玉屏索道下山回南大门。"
)


def extract_poi_sequence(text):
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
    return sum(b.size for b in SequenceMatcher(a=list(a), b=list(b)).get_matching_blocks())


def main():
    routes = json.load(open(os.path.join(OUT, "structured_routes.json"), encoding="utf-8"))
    official = next(r for r in routes if r["scenic"] == "黄山")
    official_seq = [s["spot"] for s in official["steps"]]

    tourist_seq = extract_poi_sequence(TOURIST_NOTE)

    off_set, tou_set = set(official_seq), set(tourist_seq)
    coverage = len(off_set & tou_set) / len(off_set)
    lcs = lcs_length(official_seq, tourist_seq)
    order_consistency = lcs / min(len(official_seq), len(tourist_seq))

    def period_counts(seq):
        n = len(seq); k = 3
        bounds = [round(i * n / k) for i in range(k + 1)]
        return [bounds[i+1]-bounds[i] for i in range(k)]

    result = {
        "scenic": "黄山",
        "official_seq": official_seq,
        "tourist_seq": tourist_seq,
        "metrics": {
            "coverage": round(coverage, 3),
            "order_consistency": round(order_consistency, 3),
            "official_len": len(official_seq),
            "tourist_len": len(tourist_seq),
            "missing_in_tourist": sorted(off_set - tou_set),
        },
        "time_allocation": {"official_am_noon_pm": period_counts(official_seq),
                            "tourist_am_noon_pm": period_counts(tourist_seq)},
        "tourist_note": TOURIST_NOTE,
    }
    p = os.path.join(OUT, "route_compare.json")
    json.dump(result, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("官方路线(%d站):" % len(official_seq), " -> ".join(official_seq))
    print("游客路线(%d站):" % len(tourist_seq), " -> ".join(tourist_seq))
    print("景点覆盖度 = %.1f%%" % (coverage*100))
    print("顺序一致性(LCS) = %.1f%%" % (order_consistency*100))
    print("游客遗漏景点:", sorted(off_set - tou_set))
    print("时间分配 官方(上/中/下):", period_counts(official_seq), " 游客:", period_counts(tourist_seq))

    # 对比柱状图
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    periods = ["上午", "中午", "下午"]
    off_c, tou_c = period_counts(official_seq), period_counts(tourist_seq)
    x = range(3); w = 0.35
    axes[0].bar([i-w/2 for i in x], off_c, w, label="官方路线", color="#4C72B0")
    axes[0].bar([i+w/2 for i in x], tou_c, w, label="游客实际", color="#DD8452")
    axes[0].set_xticks(list(x)); axes[0].set_xticklabels(periods)
    axes[0].set_ylabel("游览景点数"); axes[0].set_title("官方 vs 游客：时间分配对比(黄山)")
    axes[0].legend()
    axes[1].bar(["景点覆盖度", "顺序一致性"], [coverage*100, order_consistency*100],
                color=["#55A868", "#C44E52"])
    axes[1].set_ylim(0, 105); axes[1].set_ylabel("百分比 %")
    axes[1].set_title("官方-游客路线结构相似度(黄山)")
    for i, v in enumerate([coverage*100, order_consistency*100]):
        axes[1].text(i, v+2, "%.0f%%" % v, ha="center")
    plt.tight_layout()
    figp = os.path.join(FIG, "route_compare.png")
    plt.savefig(figp, dpi=150, bbox_inches="tight"); plt.close()
    print("[compare] 输出 %s 和 %s" % (p, figp))


if __name__ == "__main__":
    main()
