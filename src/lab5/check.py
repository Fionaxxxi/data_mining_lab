"""Validate source spans and accounting for the reviewed experiment 5 output."""
import csv
import json
from pathlib import Path

from extract import INPUT, OUT


def main():
    docs = {d['doc_id']: d for d in map(json.loads, INPUT.read_text(encoding='utf8').splitlines())}
    candidates = [json.loads(x) for x in (OUT / 'candidates.jsonl').read_text(encoding='utf8').splitlines()]
    pairs = [json.loads(x) for x in (OUT / 'reviewed_pairs.jsonl').read_text(encoding='utf8').splitlines()]
    mappings = json.loads((OUT / 'mapping.json').read_text(encoding='utf8'))
    stats = json.loads((OUT / 'stats.json').read_text(encoding='utf8'))
    reviews = list(csv.DictReader((OUT / 'manual_review.csv').open(encoding='utf-8-sig')))
    assert len(docs) == stats['documents'] == 18
    assert len(candidates) == stats['raw_candidates'] == len(reviews)
    assert len({r['id'] for r in candidates}) == len(candidates)
    assert stats['review_keep'] + stats['review_reject'] == len(reviews)
    assert len(pairs) == stats['before_dedup']
    assert len(mappings) == stats['after_dedup']
    assert sum(x['source_count'] for x in mappings) == len(pairs)
    assert sum(stats['by_traveler'].values()) == len(mappings)
    assert sum(stats['by_condition'].values()) == len(mappings)
    for pair in pairs:
        text = docs[pair['doc_id']]['clean_text']
        assert text[pair['condition_start']:pair['condition_end']] == pair['condition'], pair['id']
        assert text[pair['advice_start']:pair['advice_end']] == pair['advice'], pair['id']
        assert pair['condition_end'] <= pair['advice_start'], pair['id']
    for name in ('traveler_bar.svg',):
        assert (OUT / 'figures' / name).stat().st_size > 0
    print(f"LAB5 CHECK OK: {len(candidates)} candidates, {len(pairs)} reviewed pairs, {len(mappings)} mappings")


if __name__ == '__main__':
    main()
