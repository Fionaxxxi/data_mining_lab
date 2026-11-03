# -*- coding: utf-8 -*-
"""
time_hierarchy.py
=================
实验三：基于解析结果构建“上午/中午/下午”时间维度层级结构。

做法
----
1) 在原文中定位每个时段锚点（上午/中午/下午/傍晚）的字符位置；
2) 对每个景点，取其在原文中的首次出现位置，按“落在哪个时段区间”归组；
3) 输出层级结构：scenic -> periods[period] -> steps[spot/activity]；
4) 用 matplotlib 绘制时间层级结构图，保存到 figures/。
"""
import os, re, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

# 中文字体
for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

PERIODS = ["上午", "中午", "下午"]
ANCHOR2PERIOD = {"早上": "上午", "上午": "上午", "中午": "中午",
                 "下午": "下午", "傍晚": "下午", "晚上": "下午"}


def anchor_positions(text):
    pos = []
    for m in re.finditer(r"早上|上午|中午|下午|傍晚|晚上", text):
        pos.append((m.start(), ANCHOR2PERIOD[m.group()]))
    return sorted(pos)


def bucket_spot(spot, text, anchors):
    """根据景点在原文中的位置归入时段。"""
    # 取景点名核心（去掉括号注释）
    core = re.sub(r"[（(].*?[）)]", "", spot)
    idx = text.find(core)
    if idx < 0 or not anchors:
        return "上午"
    cur = "上午"
    for p, period in anchors:
        if idx >= p:
            cur = period
        else:
            break
    return cur


def build_hierarchy(route):
    text = route["text"]
    anchors = anchor_positions(text)
    steps = route["steps"]
    periods = {p: [] for p in PERIODS}
    if not steps:
        return {"scenic": route["scenic"], "format": route["detected_format"], "periods": []}

    # 判断：景点是否整体排在时段说明之前（箭头链路/编号列表常见）
    def spot_core(s):
        return re.sub(r"[（(].*?[）)]", "", s["spot"])
    if anchors:
        first_anchor = anchors[0][0]
        all_before = all(text.find(spot_core(s)) < first_anchor for s in steps if text.find(spot_core(s)) >= 0)
    else:
        all_before = False

    # 文本中实际出现的时段（去重保序）
    seen, period_seq = set(), []
    for _, per in anchors:
        if per not in seen:
            seen.add(per); period_seq.append(per)
    if not period_seq:
        period_seq = ["上午"]

    if all_before and len(period_seq) >= 2:
        # 比例分配：按时段数量把有序景点切分
        n = len(steps); k = len(period_seq)
        bounds = [round(i * n / k) for i in range(k + 1)]
        for i, per in enumerate(period_seq):
            for s in steps[bounds[i]:bounds[i + 1]]:
                periods[per].append({"step_no": s["step_no"], "spot": s["spot"], "activity": s["activity"]})
    else:
        for s in steps:
            per = bucket_spot(s["spot"], text, anchors)
            periods[per].append({"step_no": s["step_no"], "spot": s["spot"], "activity": s["activity"]})

    return {"scenic": route["scenic"], "format": route["detected_format"],
            "periods": [{"period": p, "steps": periods[p]} for p in PERIODS if periods[p]]}


def draw_hierarchy(hier, path):
    n = len(hier)
    fig, axes = plt.subplots(1, n, figsize=(5.2 * n, 5.5), squeeze=False)
    for ax, h in zip(axes[0], hier):
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
        ax.set_title("%s 游览时间层级" % h["scenic"], fontsize=13, fontweight="bold")
        y = 9.2
        # 根节点
        ax.text(5, y, h["scenic"] + "一日游路线", ha="center", va="center",
                fontsize=12, bbox=dict(boxstyle="round", fc="#4C72B0", ec="none"))
        y -= 1.2
        period_colors = {"上午": "#D6E6F5", "中午": "#FCE4D6", "下午": "#E2EFDA"}
        for pb in h["periods"]:
            per = pb["period"]
            spots = " → ".join(s["spot"] for s in pb["steps"])
            ax.text(5, y, "[%s] %s" % (per, spots), ha="center", va="center",
                    fontsize=9.5,
                    bbox=dict(boxstyle="round", fc=period_colors.get(per, "#eee"), ec="#888"))
            ax.annotate("", xy=(5, y + 0.55), xytext=(5, y + 0.9),
                        arrowprops=dict(arrowstyle="->", color="#666"))
            y -= 1.15
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def main():
    routes = json.load(open(os.path.join(OUT, "structured_routes.json"), encoding="utf-8"))
    hier = [build_hierarchy(r) for r in routes]
    p = os.path.join(OUT, "time_hierarchy.json")
    json.dump(hier, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    fig = os.path.join(FIG, "time_hierarchy.png")
    draw_hierarchy(hier, fig)
    for h in hier:
        print("=" * 50)
        print(h["scenic"])
        for pb in h["periods"]:
            print("  [%s] (%d站) %s" % (pb["period"], len(pb["steps"]),
                  " -> ".join(s["spot"] for s in pb["steps"])))
    print("[time_hierarchy] 输出 %s 和 %s" % (p, fig))


if __name__ == "__main__":
    main()
