# -*- coding: utf-8 -*-
"""
run.py — 实验三一键运行入口（黄山/九寨沟/张家界）
顺序：数据采集(爬虫) -> 数据集加载 -> 汇总数据集 -> 路线解析 -> 时间层级 -> 官方/游客对比
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    ("爬虫采集(九寨沟/张家界官方站)", "crawler/scenic_crawler.py"),
    ("加载教师数据集IndustryCorpus2", "src/load_industrycorpus.py"),
    ("汇总统一数据集", "src/build_dataset.py"),
    ("官方路线结构化解析", "src/parse_route.py"),
    ("时间维度层级构建", "src/time_hierarchy.py"),
    ("官方vs游客路线对比(黄山)", "src/compare_routes.py"),
]

if __name__ == "__main__":
    for name, rel in STEPS:
        print("\n" + "=" * 70)
        print(">>>", name)
        print("=" * 70)
        r = subprocess.run([sys.executable, os.path.join(ROOT, rel)], cwd=ROOT)
        if r.returncode != 0:
            print("[!] 步骤失败:", name)
            sys.exit(r.returncode)
    print("\n全部完成。输出见 output/ 与 figures/ 目录。")
