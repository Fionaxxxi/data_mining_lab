"""Apply documented manual review, keep offsets, and build the final mapping."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

from extract import INPUT, OUT, condition_type, normalize, traveler_type


def find_pair(text, condition, advice, around=None):
    cs = [m.start() for m in re.finditer(re.escape(condition), text)]
    ads = [m.start() for m in re.finditer(re.escape(advice), text)]
    choices = [(c, a) for c in cs for a in ads if 0 <= a - (c + len(condition)) <= 300]
    if around is not None:
        choices = [(c, a) for c, a in choices if abs(c - around) <= 300]
    if not choices:
        raise ValueError(f'Cannot locate source pair: {condition!r} -> {advice!r}')
    return min(choices, key=lambda x: (abs(x[0] - around) if around is not None else x[1] - x[0], x[1] - x[0]))


def make_record(doc, condition, advice, rule, note, around=None):
    text = doc['clean_text']
    c, a = find_pair(text, condition, advice, around)
    return {'id': f"{doc['doc_id']}:{c}:{a}", 'doc_id': doc['doc_id'], 'scenic': doc['scenic'],
            'text_type': doc['text_type'], 'source_name': doc['source_name'],
            'source_record_id': doc['source_record_id'], 'source_file': doc['source_file'],
            'source_url': doc.get('original_url') or None, 'condition': condition,
            'condition_start': c, 'condition_end': c + len(condition), 'advice': advice,
            'advice_start': a, 'advice_end': a + len(advice), 'condition_type': condition_type(condition),
            'traveler_type': traveler_type(condition + ' ' + advice), 'rule': rule, 'review_note': note,
            'needs_context_resolution': bool(re.search(r'��(?:��|��|��|��)|��(?:��|��)|����|����|����', advice)),
            'source_excerpt': text[max(0, c - 35):min(len(text), a + len(advice) + 35)]}


def merge(rows):
    groups = []
    for row in rows:
        key = (row['scenic'], normalize(row['condition']))
        matches = [g for g in groups if g['key'] == key and
                   (normalize(row['advice']) in normalize(g['advice']) or normalize(g['advice']) in normalize(row['advice']))]
        if matches:
            group = matches[0]
            group['sources'].append(row)
            if len(normalize(row['advice'])) > len(normalize(group['advice'])):
                group['advice'] = row['advice']
        else:
            groups.append({'key': key, 'condition': row['condition'], 'advice': row['advice'],
                           'condition_type': row['condition_type'], 'traveler_type': row['traveler_type'],
                           'scenic': row['scenic'], 'sources': [row]})
    for i, group in enumerate(groups, 1):
        group['mapping_id'] = f'C{i:03d}'
        del group['key']
        group['source_count'] = len(group['sources'])
        group['needs_context_resolution'] = any(s['needs_context_resolution'] for s in group['sources'])
    return groups


def main():
    docs = {d['doc_id']: d for d in map(json.loads, INPUT.read_text(encoding='utf8').splitlines())}
    raw = {r['id']: r for r in map(json.loads, (OUT / 'candidates.jsonl').read_text(encoding='utf8').splitlines())}
    review = list(csv.DictReader((OUT / 'manual_review.csv').open(encoding='utf-8-sig')))
    if {r['id'] for r in review} != set(raw):
        raise ValueError('Manual review must cover every raw candidate exactly once')
    rows = []
    for item in review:
        if item['decision'] == 'reject':
            continue
        if item['decision'] != 'keep':
            raise ValueError(item)
        source = raw[item['id']]
        rows.append(make_record(docs[source['doc_id']], item['condition'], item['advice'],
                                'reviewed_' + source['trigger'], item['reason'], source['condition_start']))
    supplement = list(csv.DictReader((OUT / 'manual_supplements.csv').open(encoding='utf-8-sig')))
    for item in supplement:
        rows.append(make_record(docs[item['doc_id']], item['condition'], item['advice'],
                                'manual_supplement', item['reason']))
    mappings = merge(rows)
    with (OUT / 'reviewed_pairs.jsonl').open('w', encoding='utf8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    (OUT / 'mapping.json').write_text(json.dumps(mappings, ensure_ascii=False, indent=2), encoding='utf8')
    with (OUT / 'mapping.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['mapping_id', 'scenic', 'traveler_type', 'condition_type', 'condition', 'advice', 'needs_context_resolution', 'source_count', 'source_ids'])
        for m in mappings:
            writer.writerow([m['mapping_id'], m['scenic'], m['traveler_type'], m['condition_type'],
                             m['condition'], m['advice'], m['needs_context_resolution'], m['source_count'], ';'.join(s['id'] for s in m['sources'])])
    stats = {'documents': len(docs), 'raw_candidates': len(raw), 'review_keep': sum(x['decision'] == 'keep' for x in review),
             'review_reject': sum(x['decision'] == 'reject' for x in review), 'manual_supplements': len(supplement),
             'before_dedup': len(rows), 'after_dedup': len(mappings),
             'by_traveler': dict(Counter(m['traveler_type'] for m in mappings)),
             'by_condition': dict(Counter(m['condition_type'] for m in mappings)),
             'by_scenic': dict(Counter(m['scenic'] for m in mappings))}
    stats['needs_context_resolution'] = sum(m['needs_context_resolution'] for m in mappings)
    stats['candidate_acceptance_rate'] = stats['review_keep'] / stats['raw_candidates']
    stats['first_pass_share_of_known_pairs'] = stats['review_keep'] / stats['before_dedup']
    (OUT / 'stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()
