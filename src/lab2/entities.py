"""Experiment 2: reproducible, rule-based tourism entity extraction.

Only Python's standard library is required. All offsets refer to clean_text,
use zero-based Python character indexes, and have exclusive ends.
"""

from __future__ import annotations

import argparse
import collections
import csv
import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "outputs" / "cleaned_data.jsonl"
DEFAULT_OUTPUT = ROOT / "outputs" / "lab2"

# Named places were checked against the three official routes and travel notes.
# Keep scenic names in separate lists to make cross-scenic reuse and audit easy.
POI = {
    "黄山": "黄山,云谷寺,云谷寺索道站,白鹅岭,白鹅岭站,始信峰,北海景区,北海宾馆,西海饭店,西海大峡谷,西海大峡谷谷底,排云亭,丹霞站,白云宾馆,光明顶,海心亭,鳌鱼峰,莲花亭,迎客松,玉屏楼,梦笔生花,猴子观海,曙光亭,黑虎松,飞来石,连理松,龙爪松,天都峰,莲花峰,百步云梯,一线天,慈光阁,温泉景区,狮子峰,清凉台,猴子观海,丹霞峰,太平湖,宏村,屯溪老街,老街,汤口镇,汤口,换乘中心,北大门,南大门,北门,南门,西门,东门,黄山北站,黄山机场,高铁站,翡翠谷,九龙瀑,新安江,徽州古城,西递,黄山风景区".split(","),
    "九寨沟": "九寨沟,九寨沟风景区,沟口,原始森林,芳草海,天鹅海,箭竹海,熊猫海,五花海,珍珠滩,珍珠滩瀑布,镜海,诺日朗,诺日朗瀑布,诺日朗换乘站,长海,五彩池,树正寨,树正瀑布,树正群海,盆景滩,犀牛海,老虎海,火花海,芦苇海,双龙海,卧龙海,扎如寺,日则沟,则查洼沟,树正沟,九黄机场,黄龙,黄龙景区,成都,都江堰,松潘,川主寺,漳扎镇,九寨沟县,九寨天堂".split(","),
    "张家界": "张家界,武陵源,武陵源景区,武陵源景区东门,武陵源景区南门,武陵源景区西门,武陵源东门,武陵源南门,武陵源西门,天子山,袁家界,十里画廊,黄石寨,金鞭溪,杨家界,百龙天梯,天门山,天门洞,张家界国家森林公园,张家界大峡谷,黄龙洞,龙王洞,宝峰湖,索溪峪,水绕四门,老屋场,空中田园,乌龙寨,天下第一桥,迷魂台,御笔峰,贺龙公园,大观台,神堂湾,点将台,金鞭岩,紫草潭,千里相会,凤凰古城,芙蓉镇,张家界千古情,魅力湘西,张家界西站,张家界机场".split(","),
}

# Longer terms win. POI names are locations, while cableways are transport.
TRANSPORT = "西海大峡谷观光缆车,云谷索道,玉屏索道,太平索道,百龙天梯,天门山索道,黄石寨索道,观光缆车,观光车,摆渡车,景区大巴,机场大巴,公交车,公交,班车,大巴车,大巴,专车,出租车,网约车,小火车,缆车,索道,动车,高铁,火车,飞机,自驾,徒步,步行,骑行,打车,乘车,开车".split(",")
TRANSPORT_ALIASES = {"大巴车": "大巴", "景区大巴": "大巴", "机场大巴": "大巴", "观光缆车": "缆车", "西海大峡谷观光缆车": "缆车", "云谷索道": "索道", "玉屏索道": "索道", "太平索道": "索道", "黄石寨索道": "索道", "天门山索道": "索道", "公交车": "公交", "打车": "出租车", "网约车": "出租车", "乘车": "乘车"}
POI_ALIASES = {"老街": "屯溪老街", "武陵源东门": "武陵源景区东门", "武陵源南门": "武陵源景区南门", "武陵源西门": "武陵源景区西门"}
POI["黄山"].append("白鹅山庄")
POI["九寨沟"].extend(["诺日朗中心站", "神仙池"])
POI_ALIASES["诺日朗中心站"] = "诺日朗换乘站"

TIME_RULES = [
    ("clock_range", re.compile(r"(?<!\d)(?:[01]?\d|2[0-3])[:：][0-5]\d\s*[-~～—至到]\s*(?:[01]?\d|2[0-3])[:：][0-5]\d(?!\d)")),
    ("clock", re.compile(r"(?<!\d)(?:[01]?\d|2[0-3])[:：][0-5]\d(?!\d)")),
    ("hour", re.compile(r"(?<![\d第])(?:凌晨|清晨|早上|上午|中午|下午|傍晚|晚上|夜里)?\s*(?:[01]?\d|2[0-3])点(?:半|[0-5]?\d分?)?")),
    ("chinese_hour", re.compile(r"(?:凌晨|清晨|早上|上午|中午|下午|傍晚|晚上|夜里)\s*[一二两三四五六七八九十]{1,3}点(?:半|[一二三四五六七八九十]{1,2}分)?|(?<!第)[一二两三四五六七八九十]{1,3}点(?:半|[一二三四五六七八九十]{1,2}分)")),
    ("daypart", re.compile(r"上午|中午|下午|早上|清晨|傍晚|晚上|夜里|凌晨|日出|日落")),
    ("duration", re.compile(r"(?<!第)(?:约|大约|差不多)?\s*(?:\d+(?:\.\d+)?|[一二两三四五六七八九十半]+)\s*(?:个)?\s*(?:小时|分钟|天)(?:左右|多)?")),
]
TIME_EXCLUSIONS = re.compile(r"(?:\d{4}年|\d+月\d+日|第\d+天)")
OUT_OF_SCOPE = {"成都", "都江堰", "松潘", "川主寺", "黄龙", "黄龙景区", "凤凰古城", "芙蓉镇", "宏村", "西递", "徽州古城", "太平湖", "新安江"}
BASELINE_HOUR = re.compile(r"(?<!\d)(?:凌晨|清晨|早上|上午|中午|下午|傍晚|晚上|夜里)?\s*(?:[一二两三四五六七八九十\d]{1,3})点(?:半|[一二三四五六七八九十\d]{1,2}分)?")
BASELINE_DURATION = re.compile(r"(?:约|大约|差不多)?\s*(?:\d+(?:\.\d+)?|[一二两三四五六七八九十半]+)\s*(?:个)?\s*(?:小时|分钟|天)(?:左右|多)?")


def load_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Input contains no records")
    ids = [row["doc_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate doc_id in input")
    for row in rows:
        if row["scenic"] not in POI or not isinstance(row.get("clean_text"), str):
            raise ValueError(f"Missing or unsupported fields in {row.get('doc_id')}")
    return rows


def phrase_matches(text: str, words: list[str], entity_type: str, scenic: str) -> list[dict]:
    matches = []
    for word in sorted(set(words), key=lambda x: (-len(x), x)):
        for hit in re.finditer(re.escape(word), text):
            start, end = hit.span()
            # Avoid bare place names inside a longer compound place name.
            if entity_type == "POI" and word in {"黄山", "九寨沟", "张家界", "武陵源", "老街", "黄龙", "汤口", "沟口"}:
                if end < len(text) and text[end:end + 2] in {"机场", "景区", "风景", "北站", "西站", "索道", "宾馆", "县", "镇"}:
                    continue
            canonical = (POI_ALIASES if entity_type == "POI" else TRANSPORT_ALIASES).get(word, word)
            matches.append(dict(text=word, canonical=canonical, type=entity_type, start=start, end=end, rule="domain_lexicon", scenic=scenic))
    return matches


def time_matches(text: str, scenic: str) -> list[dict]:
    matches = []
    for name, pattern in TIME_RULES:
        for hit in pattern.finditer(text):
            word = hit.group().strip()
            start = hit.start() + len(hit.group()) - len(hit.group().lstrip())
            if TIME_EXCLUSIONS.fullmatch(word):
                continue
            matches.append(dict(text=word, canonical=word, type="TIME", start=start, end=hit.end(), rule=name, scenic=scenic))
    return matches


def resolve_overlaps(candidates: list[dict]) -> list[dict]:
    priority = {"POI": 0, "TRANSPORT": 1, "TIME": 2}
    # A named facility such as 百龙天梯 is a transport mention, not a POI.
    candidates = [m for m in candidates if not (m["type"] == "POI" and m["text"] == "百龙天梯")]
    candidates.sort(key=lambda m: (-(m["end"] - m["start"]), priority[m["type"]], m["start"]))
    kept = []
    for item in candidates:
        if not any(item["start"] < prev["end"] and prev["start"] < item["end"] for prev in kept):
            kept.append(item)
    return sorted(kept, key=lambda m: (m["start"], m["end"]))


def extract(row: dict) -> list[dict]:
    text = row["clean_text"]
    scenic = row["scenic"]
    candidates = phrase_matches(text, [p for p in POI[scenic] if p not in OUT_OF_SCOPE], "POI", scenic)
    candidates += phrase_matches(text, TRANSPORT, "TRANSPORT", scenic)
    candidates += time_matches(text, scenic)
    result = resolve_overlaps(candidates)
    for item in result:
        item.update(doc_id=row["doc_id"], text_type=row["text_type"], source_name=row["source_name"], source_url=row.get("source_url", ""), context=text[max(0, item["start"] - 22):min(len(text), item["end"] + 22)])
        if text[item["start"]:item["end"]] != item["text"]:
            raise AssertionError(f"Offset mismatch: {row['doc_id']} {item}")
    return result


def baseline_extract(row: dict) -> list[dict]:
    """Reconstruct the first-pass rules for a transparent iteration comparison."""
    text, scenic = row["clean_text"], row["scenic"]
    candidates = phrase_matches(text, POI[scenic], "POI", scenic)
    candidates += phrase_matches(text, TRANSPORT, "TRANSPORT", scenic)
    for name, pattern in TIME_RULES:
        if name in {"hour", "chinese_hour", "duration"}:
            continue
        candidates += [dict(text=m.group(), canonical=m.group(), type="TIME", start=m.start(), end=m.end(), rule=name, scenic=scenic) for m in pattern.finditer(text)]
    for name, pattern in (("hour", BASELINE_HOUR), ("duration", BASELINE_DURATION)):
        candidates += [dict(text=m.group().strip(), canonical=m.group().strip(), type="TIME", start=m.start() + len(m.group()) - len(m.group().lstrip()), end=m.end(), rule=name, scenic=scenic) for m in pattern.finditer(text)]
    return resolve_overlaps(candidates)


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_svg(path: Path, title: str, counts: collections.Counter, color: str) -> None:
    top = counts.most_common(15)
    width, row_h, left, top_y = 900, 35, 220, 75
    height = top_y + row_h * max(1, len(top)) + 45
    max_n = max((n for _, n in top), default=1)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', f'<text x="28" y="42" font-size="24" font-family="Microsoft YaHei, sans-serif">{html.escape(title)}</text>']
    for i, (label, count) in enumerate(top):
        y = top_y + i * row_h
        bar = round((width - left - 95) * count / max_n)
        parts += [f'<text x="28" y="{y + 20}" font-size="17" font-family="Microsoft YaHei, sans-serif">{html.escape(label)}</text>', f'<rect x="{left}" y="{y + 3}" width="{bar}" height="23" fill="{color}"/>', f'<text x="{left + bar + 9}" y="{y + 21}" font-size="16">{count}</text>']
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    rows = load_rows(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    entities = [entity for row in rows for entity in extract(row)]
    save_json(args.output / "entities.json", {"offset_convention": "clean_text, zero-based Python character offsets, end-exclusive", "entities": entities})
    with (args.output / "entities.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["doc_id", "scenic", "text_type", "type", "text", "canonical", "start", "end", "rule", "source_name", "source_url", "context"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{k: e.get(k, "") for k in fields} for e in entities])
    counts = {kind: collections.Counter(e["canonical"] for e in entities if e["type"] == kind) for kind in ("POI", "TRANSPORT", "TIME")}
    by_scenic = {scenic: dict(collections.Counter(e["type"] for e in entities if e["scenic"] == scenic)) for scenic in POI}
    stats = {"documents": len(rows), "mentions": len(entities), "by_type": dict(collections.Counter(e["type"] for e in entities)), "by_scenic": by_scenic, "unique_canonical": {key: len(value) for key, value in counts.items()}, "top": {key: value.most_common(20) for key, value in counts.items()}, "offset_convention": "clean_text, zero-based Python character offsets, end-exclusive"}
    save_json(args.output / "stats.json", stats)
    baseline = [item for row in rows for item in baseline_extract(row)]
    save_json(args.output / "iteration.json", {"baseline_mentions": len(baseline), "baseline_by_type": dict(collections.Counter(e["type"] for e in baseline)), "refined_mentions": len(entities), "refined_by_type": stats["by_type"], "changes": ["Excluded out-of-scope neighboring cities and unrelated attractions from POI lexicon", "Tightened hour and duration regex to avoid 一点 in degree expressions and 二天 inside 第二天", "Included expressions such as 6点45 and 下午三点半"]})
    for kind, color in (("POI", "#2374ab"), ("TRANSPORT", "#268a60"), ("TIME", "#be6830")):
        write_svg(args.output / f"frequency_{kind.lower()}.svg", f"{kind} 实体词频（规范名，前15）", counts[kind], color)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
