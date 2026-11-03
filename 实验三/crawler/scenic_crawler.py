# -*- coding: utf-8 -*-
"""
scenic_crawler.py
==================
景区游览数据补充爬虫（实验一数据采集的补充，服务于实验三）。

目标
----
补充采集两类文本：
1) 景区官方推荐路线（官方游览指南 / 官网导览页 / 官方攻略）；
2) 游客游记（游客分享的实际游览经历）。

技术栈
------
requests + BeautifulSoup(lxml)。带浏览器请求头、失败重试、礼貌延迟，
自动去除 <script>/<style>/导航等噪声，抽取正文段落，并按是否含旅游关键词过滤。

用法
----
    python crawler/scenic_crawler.py
输出
----
    data/raw/crawled_pages.json   每条含 url/title/source/text_type/paragraphs/content
"""
import os, re, json, time, random
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 种子 URL：官方 / 攻略类页面。可自行增删。
# text_type 标注该页预期是 official(官方路线) 还是 note(游客游记)。
SEEDS = [
    # —— 故宫博物院 ——
    {"url": "https://www.dpm.org.cn/Home.html", "scenic": "故宫", "text_type": "official"},
    # —— 颐和园 ——
    {"url": "https://www.summerpalace-china.com/", "scenic": "颐和园", "text_type": "official"},
    # —— 携程目的地攻略（静态可访问） ——
    {"url": "https://ct.ctrip.com/", "scenic": "综合", "text_type": "note"},
    # —— 知乎游览话题（公开可访问） ——
    {"url": "https://www.zhihu.com/", "scenic": "综合", "text_type": "note"},
]

# 正文段落需命中的旅游关键词，否则视为导航/广告噪声丢弃
PARA_KW = ["景区", "游览", "游玩", "游记", "攻略", "路线", "行程", "出发",
           "景点", "门票", "开放", "参观", "上午", "下午", "中午", "推荐",
           "故宫", "颐和园", "长廊", "佛香阁", "十七孔桥", "太和殿", "御花园"]


def fetch(url, retries=2):
    for i in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            # 自动编码
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except Exception as e:
            if i == retries:
                return None
            time.sleep(1.5)
    return None


def extract_main_text(html):
    """用 BeautifulSoup 去掉 script/style/nav/footer，抽取正文段落。"""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    paras = []
    for p in soup.find_all(["p", "div", "li", "h1", "h2", "h3"]):
        t = re.sub(r"\s+", " ", p.get_text()).strip()
        if 15 <= len(t) <= 400:
            paras.append(t)
    # 去重保序
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
        content = "\n".join(tourism)
        results.append({
            "url": url, "scenic": seed["scenic"], "text_type": seed["text_type"],
            "ok": True, "title": title,
            "paragraphs": tourism, "content": content,
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
