# -*- coding: utf-8 -*-
"""
scenic_crawler.py
==================
景区游览数据补充爬虫（实验三：黄山 / 九寨沟 / 张家界）。

目标：补充采集三个景区的官方游览信息（开放时间、门票、导览、游览推荐）。
技术：requests + BeautifulSoup(lxml)，带浏览器请求头、失败重试、礼貌延迟，
自动去除 <script>/<style>/导航等噪声，抽取正文段落并按旅游关键词过滤。

输出：data/lab3/raw/crawled_pages.json
"""
import os, re, json, time, random
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(ROOT, "data", "lab3", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 三个景区的可访问官方/官方媒体来源
SEEDS = [
    {"url": "https://www.cnhuangshan.com/", "scenic": "黄山", "text_type": "official"},
    {"url": "https://www.jiuzhai.com/", "scenic": "九寨沟", "text_type": "official"},
    {"url": "https://www.zjj.gov.cn/", "scenic": "张家界", "text_type": "official"},
    {"url": "https://zjj.rednet.cn/", "scenic": "张家界", "text_type": "official"},
]

PARA_KW = ["景区", "游览", "游玩", "攻略", "路线", "行程", "出发",
           "景点", "门票", "开放", "参观", "上午", "下午", "中午", "推荐",
           "黄山", "九寨沟", "张家界", "索道", "栈道", "海子", "迎客松",
           "光明顶", "袁家界", "天子山", "金鞭溪", "五花海", "五彩池"]


def fetch(url, retries=2):
    for i in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except Exception:
            if i == retries:
                return None
            time.sleep(1.5)
    return None


def extract_main_text(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    paras = []
    for p in soup.find_all(["p", "div", "li", "h1", "h2", "h3"]):
        t = re.sub(r"\s+", " ", p.get_text()).strip()
        if 15 <= len(t) <= 500:
            paras.append(t)
    seen, uniq = set(), []
    for t in paras:
        if t not in seen:
            seen.add(t); uniq.append(t)
    return title, uniq


def looks_like_tourism(paras):
    return [p for p in paras if any(k in p for k in PARA_KW)]


def main():
    results = []
    for seed in SEEDS:
        url = seed["url"]
        print("[crawl]", url)
        html = fetch(url)
        if not html:
            print("   -> 失败/被拦截:", url)
            results.append({"url": url, "scenic": seed["scenic"],
                            "text_type": seed["text_type"], "ok": False,
                            "title": "", "paragraphs": [], "content": ""})
            time.sleep(random.uniform(1.0, 2.0))
            continue
        title, paras = extract_main_text(html)
        tourism = looks_like_tourism(paras)
        results.append({
            "url": url, "scenic": seed["scenic"], "text_type": seed["text_type"],
            "ok": True, "title": title, "paragraphs": tourism,
            "content": "\n".join(tourism),
            "raw_para_count": len(paras), "tourism_para_count": len(tourism),
        })
        print("   -> ok, 正文段 %d, 旅游相关段 %d" % (len(paras), len(tourism)))
        time.sleep(random.uniform(1.0, 2.0))

    out = os.path.join(RAW_DIR, "crawled_pages.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in results if r["ok"])
    print("[crawl] 完成: 成功 %d/%d, 输出 -> %s" % (ok, len(results), out))


if __name__ == "__main__":
    main()
