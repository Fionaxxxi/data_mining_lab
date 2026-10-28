"""Check Lab 2 output integrity and representative recognition boundaries."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lab2_entities import extract, load_rows


def main():
    rows = load_rows(ROOT / "outputs" / "cleaned_data.jsonl")
    by_id = {row["doc_id"]: row for row in rows}
    actual = {row["doc_id"]: extract(row) for row in rows}
    saved = json.loads((ROOT / "outputs" / "lab2" / "entities.json").read_text(encoding="utf-8"))["entities"]
    assert len(saved) == sum(map(len, actual.values()))
    assert {e["doc_id"] for e in saved} == set(by_id)
    for e in saved:
        text = by_id[e["doc_id"]]["clean_text"]
        assert text[e["start"]:e["end"]] == e["text"]
        assert e["type"] in {"POI", "TRANSPORT", "TIME"}
    # These checks correspond to recognizable source spans, not fabricated data.
    positive = [
        ("HS-O01", "太平索道", "TRANSPORT"),
        ("HS-O01", "排云亭", "POI"),
        ("HS-O01", "西海大峡谷谷底", "POI"),
        ("JZG-O01", "原始森林", "POI"),
        ("JZG-O01", "7:00-8:10", "TIME"),
        ("JZG-O01", "步行", "TRANSPORT"),
        ("ZJJ-O01", "天子山", "POI"),
        ("ZJJ-O01", "自驾", "TRANSPORT"),
        ("HS-T01", "6点45", "TIME"),
        ("HS-T02", "16:30", "TIME"),
    ]
    for doc_id, surface, kind in positive:
        assert any(surface in e["text"] and e["type"] == kind for e in actual[doc_id]), (doc_id, surface, kind)
    negative = [
        ("HS-T01", "一点", "TIME"),
        ("HS-T01", "二天", "TIME"),
        ("JZG-T01", "成都", "POI"),
        ("ZJJ-T03", "凤凰古城", "POI"),
    ]
    for doc_id, surface, kind in negative:
        assert not any(e["text"] == surface and e["type"] == kind for e in actual[doc_id]), (doc_id, surface, kind)
    result = {"documents": len(rows), "checked_mentions": len(saved), "positive_cases": len(positive), "negative_cases": len(negative), "offset_errors": 0, "status": "passed"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
