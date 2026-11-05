# -*- coding: utf-8 -*-
"""
load_industrycorpus.py
======================
加载教师提供的数据集 BAAI/IndustryCorpus2（modelscope），
从中筛选与 黄山/九寨沟/张家界 及 旅游/景区/游记 相关的中文语料，
作为实验三游客叙述补充语料。
输出：data/lab3/processed/industrycorpus_tourism_sample.json
"""
import os, re, json, time
import requests
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(ROOT, "data", "lab3", "raw")
OUT_DIR = os.path.join(ROOT, "data", "lab3", "processed")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

FILE_PATH = "accommodation_catering_hotel/chinese/low/rank_00139.parquet"
DOWNLOAD_URL = (
    "https://www.modelscope.cn/api/v1/datasets/BAAI/IndustryCorpus2/repo"
    f"?Revision=master&FilePath={FILE_PATH}"
)
LOCAL_PARQUET = os.path.join(RAW_DIR, "industrycorpus_" + os.path.basename(FILE_PATH))

TOURISM_KW = ["景区", "游览", "游玩", "游记", "攻略", "一日游", "二日游",
              "景点", "游客", "路线", "行程", "黄山", "九寨沟", "张家界",
              "索道", "光明顶", "迎客松", "五彩池", "五花海", "袁家界",
              "天子山", "金鞭溪"]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def download_parquet():
    if os.path.exists(LOCAL_PARQUET) and os.path.getsize(LOCAL_PARQUET) > 1_000_000:
        print("[IndustryCorpus2] 使用已缓存:", LOCAL_PARQUET)
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
    print("[IndustryCorpus2] 下载完成 %.1f MB" % (os.path.getsize(LOCAL_PARQUET) / 1e6))
    return LOCAL_PARQUET


def main(max_samples=40):
    path = download_parquet()
    df = pd.read_parquet(path)
    print("[IndustryCorpus2] 总行数:", len(df), "列:", list(df.columns))
    # 文本列
    text_col = max(df.columns, key=lambda c: df[c].astype(str).str.len().mean()
                   if df[c].astype(str).str.len().mean() > 0 else -1)
    df[text_col] = df[text_col].astype(str)
    pat = re.compile("|".join(TOURISM_KW))
    sub = df[df[text_col].str.contains(pat)].copy()
    print("[IndustryCorpus2] 命中旅游关键词行数:", len(sub))

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
    print("[IndustryCorpus2] 写出 %d 条 -> %s" % (len(samples), out))
    for s in samples[:2]:
        print("-" * 60); print(s["content"][:250])


if __name__ == "__main__":
    main()
