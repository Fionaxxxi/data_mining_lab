# -*- coding: utf-8 -*-
"""
make_screenshot.py
==================
把 run.py 的完整运行日志（output/_run_full.txt）渲染成一张“运行结果截图”图片，
作为实验报告中“运行证据”的可视化呈现。
同时把两张结果图（时间层级图、官方-游客对比图）作为独立截图一并交付。
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "figures")

for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

LOG = os.path.join(ROOT, "output", "_run_full.txt")


def render_log_screenshot(log_path, out_png):
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    # 去掉空行，限制行数保证可读
    lines = [ln.rstrip() for ln in lines if ln.strip()]
    n = len(lines)
    # 每行等宽绘制
    fig_h = 0.30 * n + 0.6
    fig, ax = plt.subplots(figsize=(13.5, max(fig_h, 6)))
    ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    # 深色终端风格
    ax.set_facecolor("#1e1e1e")
    fig.patch.set_facecolor("#1e1e1e")
    text = "\n".join(lines)
    ax.text(0.01, 0.99, text, va="top", ha="left", fontsize=7.5,
            family="Microsoft YaHei", color="#d8d8d8", linespacing=1.35)
    ax.set_title("实验三 运行结果截图（python run.py）", color="#ffffff",
                 fontsize=13, fontweight="bold", pad=10)
    plt.savefig(out_png, dpi=150, bbox_inches="tight", facecolor="#1e1e1e")
    plt.close()
    print("运行结果截图已生成:", out_png)


if __name__ == "__main__":
    if os.path.exists(LOG):
        render_log_screenshot(LOG, os.path.join(FIG, "run_screenshot.png"))
    else:
        print("未找到运行日志:", LOG)
