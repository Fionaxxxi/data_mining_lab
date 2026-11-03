# -*- coding: utf-8 -*-
"""
load_industrycorpus.py
======================
加载教师提供的数据集 BAAI/IndustryCorpus2（modelscope），从中筛选与“旅游 / 景区 / 游览 / 游记”
相关的中文语料，作为实验三“游客游记 / 真实游览叙述”的补充语料来源。

数据集说明
----------
- 来源：https://www.modelscope.cn/datasets/BAAI/IndustryCorpus2
- 结构：按行业分目录（住宿餐饮酒店 accommodation_catering_hotel、航空航天……），
        每个行业下分 chinese/english × high/middle/low 质量档，parquet 存储。
- 与旅游最相关的是 accommodation_catering_hotel（住宿餐饮酒店）行业目录。
- 单文件数百 MB，本脚本只下载“最小的中文文件”并在内存中按关键词过滤，
  抽取若干条与景区游览相关的文本，落盘为 JSON，供后续流程使用。

用法
----
    python src/load_industrycorpus.py
输出
----
    data/processed/industrycorpus_tourism_sample.json
"""
import os, sys, json, time, re, hashlib
import requests
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "data", "processed")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# 选用：住宿餐饮酒店 / 中文 / 低质量档里最小的一个 parquet（约 44MB），足够抽样
FILE_PATH = "accommodation_catering_hotel/chinese/low/rank_00139.parquet"
DOWNLOAD_URL = (
    "https://www.modelscope.cn/api/v1/datasets/BAAI/IndustryCorpus2/repo"
    f"?Revision=master&FilePath={FILE_PATH}"
)
LOCAL_PARQUET = os.path.join(RAW_DIR, "industrycorpus_" + os.path.basename(FILE_PATH))

# 旅游相关关键词：命中任一即认为是旅游叙述文本
TOURISM_KW = ["景区", "游览", "游玩", "游记", "攻略", "一日游", "二日游", "门票",
              "景点", "游客", "导游", "出发", "路线", "行程", "酒店", "住宿",
              "故宫", "颐和园", "西湖", "长城", "泰山", "黄山", "兵马俑"]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def download_parquet():
    if os.path.exists(LOCAL_PARQUET) and os.path.getsize(LOCAL_PARQUET) > 1_000_000:
        print("[IndustryCorpus2] 使用已缓存文件:", LOCAL_PARQUET)
        return LOCAL_PARQUET
    print("[IndustryCorpus2] 下载:", DOWNLOAD_URL)
    with requests.get(DOWNLOAD_URL, headers=HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        tmp = LOCAL_PARQUET + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
        os.replace(tmp, LOCAL_PARQUET)
    print("[IndustryCorpus2] 下载完成, 大小 %.1f MB" % (os.path.getsize(LOCAL_PARQUET) / 1e6))
    return LOCAL_PARQUET


def pick_text_column(df):
    """parquet 列名可能是 text/content/raw_content，自动挑选最长文本列。"""
    best, best_len = None, -1
    for col in df.columns:
        s = df[col].dropna().astype(str)
        if len(s) == 0:
            continue
        avg = s.str.len().mean()
        if avg > best_len:
            best, best_len = col, avg
    return best


def main(max_samples=40):
    path = download_parquet()
    print("[IndustryCorpus2] 读取 parquet ...")
    df = pd.read_parquet(path)
    print("[IndustryCorpus2] 总行数:", len(df), "列:", list(df.columns))
    text_col = pick_text_column(df)
    print("[IndustryCorpus2] 文本列:", text_col)

    df[text_col] = df[text_col].astype(str)
    # 命中旅游关键词的行
    pat = re.compile("|".join(TOURISM_KW))
    mask = df[text_col].str.contains(pat)
    sub = df[mask].copy()
    print("[IndustryCorpus2] 命中旅游关键词行数:", len(sub))

    # 按长度适中（200~2000 字）抽取，过长的截断
    samples = []
    for _, row in sub.iterrows():
        txt = re.sub(r"\s+", " ", str(row[text_col])).strip()
        if not (150 <= len(txt) <= 2500):
            continue
        samples.append({
            "source": "IndustryCorpus2(BAAI)",
            "file": FILE_PATH,
            "text_type": "旅游相关语料(自动抽取)",
            "content": txt[:2000],
            "char_len": len(txt),
        })
        if len(samples) >= max_samples:
            break

    out = os.path.join(OUT_DIR, "industrycorpus_tourism_sample.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print("[IndustryCorpus2] 已写出 %d 条 -> %s" % (len(samples), out))
    # 打印前 2 条预览
    for s in samples[:2]:
        print("-" * 60)
        print(s["content"][:300])


if __name__ == "__main__":
    main()
