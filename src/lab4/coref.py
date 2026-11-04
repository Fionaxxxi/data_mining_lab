"""Reproducible rule baseline and manually auditable evaluation for lab 4."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs' / 'lab4'
OUT.mkdir(parents=True, exist_ok=True)
IDS = ('HS-T01', 'HS-T02', 'JZG-T02', 'ZJJ-T01')
PRON = re.compile('那里|他们|它们|这儿|那儿|它|这|那')
SENT = re.compile(r'[^。！？!?；;\.\n]+[。！？!?；;\.]?')
PEOPLE = ('游客', '导游', '朋友', '同伴', '挑夫')
GENERIC_PLACE = re.compile(r'(?:(?:[\u4e00-\u9fff]{2,6})(?:地区|国有林场|自然风景区|旅游景区)|路口)')
MOTION = re.compile(r'登上|游览|到达|到了|前往|来到|在|住在')


def detect(doc):
    text = doc['clean_text']
    for sent in SENT.finditer(text):
        for match in PRON.finditer(sent.group()):
            start = sent.start() + match.start()
            token = match.group()
            if skip_reason(text, start, token):
                continue
            yield {'id': f"{doc['doc_id']}:{start}", 'doc_id': doc['doc_id'],
                   'scenic': doc['scenic'], 'source_record_id': doc['source_record_id'],
                   'source_file': doc['source_file'], 'sentence': sent.group(),
                   'sentence_start': sent.start(), 'pronoun': token,
                   'pronoun_start': start, 'pronoun_end': start + len(token),
                   'context': text[max(0, start - 90):min(len(text), start + 70)]}


def skip_reason(text, start, token):
    following = text[start + len(token):start + len(token) + 1]
    if token in ('这', '那') and following in '个些样次么条段颗张天时边':
        return 'modifier_with_classifier'
    return None


def predict(row, text, entities):
    start = row['pronoun_start']
    pronoun = row['pronoun']
    if pronoun == '它' and start > 0 and text[start - 1] == '其':
        return None
    if pronoun == '那' and text[start:start + 3] == '那雅兴':
        return None
    if pronoun == '他们':
        pool = [e for e in entities if e['end'] <= start and e['type'] == 'person']
    elif pronoun in ('那里', '这儿', '那儿'):
        pool = [e for e in entities if e['end'] <= start and e['type'] in ('place', 'ordinary_place')]
    else:
        pool = [e for e in entities if e['end'] <= start and e['type'] != 'person']
    pool = [e for e in pool if start - e['end'] <= 220]
    if not pool:
        return None
    # In "A 与 B 相比，但它...", B is the comparison target, not the
    # continuing subject A. Prefer the closest entity before 与.
    recent = text[max(0, start - 80):start]
    compare = list(re.finditer(r'与[^。！？\n]{0,25}相比', recent))
    if compare and pronoun == '它':
        boundary = max(0, start - 80) + compare[-1].start()
        topics = [e for e in pool if e['end'] <= boundary and boundary - e['end'] <= 60]
        if topics:
            return max(topics, key=lambda e: e['end'])
    # In a description "A 是...，在...这里", the descriptive subject is
    # usually A, even when a broader region occurs inside the description.
    if pronoun in ('这', '那里', '这儿', '那儿'):
        segment = text[max(0, start - 130):start]
        descriptions = list(re.finditer(r'是[^。！？\n]{0,90}在[^。！？\n]{0,30}$', segment))
        if descriptions:
            boundary = max(0, start - 130) + descriptions[-1].start()
            subjects = [e for e in pool if e['end'] <= boundary and boundary - e['end'] <= 20]
            if subjects:
                return max(subjects, key=lambda e: e['end'])
    def rank(entity):
        distance = start - entity['end']
        prefix = text[max(0, entity['start'] - 8):entity['start']]
        score = -distance
        # A destination in the recent narrative is more salient than a place
        # mentioned only as a comparison or as a geographic modifier.
        if MOTION.search(prefix) and prefix.rstrip().endswith(('登上', '游览', '到达', '到了', '前往', '来到', '在', '住在')):
            score += 45
        if prefix.endswith(('与', '和', '比', '相比')):
            score -= 75
        if entity['text'] in ('黄山', '九寨沟', '张家界') and text[entity['end']:entity['end'] + 2] in ('第二', '第一', '最高'):
            score -= 65
        if entity['type'] == 'ordinary_place' and pronoun in ('这里', '那里', '这儿', '那儿', '这'):
            score += 12
        return (score, entity['end'])
    return max(pool, key=rank)


def build_entities(doc_id, text, lab2):
    entities = []
    for item in lab2:
        if item['doc_id'] == doc_id and item['type'] == 'POI' and text[item['start']:item['end']] == item['text']:
            entities.append({'text': item['text'], 'start': item['start'], 'end': item['end'], 'type': 'place'})
    for match in GENERIC_PLACE.finditer(text):
        value = match.group()
        start_pos = match.start()
        for separator in ('去', '到', '游览', '前往', '来到'):
            if separator in value:
                cut = value.rfind(separator) + len(separator)
                start_pos += cut
                value = value[cut:]
        if value.endswith(('自然风景区', '旅游景区')):
            for known in sorted((e for e in entities if e['end'] <= match.end() and e['start'] >= start_pos), key=lambda e: e['start']):
                if text[known['end']:match.end()] in ('自然风景区', '旅游景区'):
                    value = text[known['start']:match.end()]
                    start_pos = known['start']
                    break
        entities.append({'text': value, 'start': start_pos, 'end': match.end(), 'type': 'ordinary_place'})
    for match in re.finditer('游客|导游|朋友|同伴|挑夫', text):
        entities.append({'text': match.group(), 'start': match.start(), 'end': match.end(), 'type': 'person'})
    return entities


def main():
    docs = {d['doc_id']: d for d in map(json.loads, (ROOT / 'outputs' / 'cleaned_data.jsonl').open(encoding='utf8')) if d['doc_id'] in IDS}
    rows = []
    detection_audit = []
    lab2 = json.loads((ROOT / 'outputs' / 'lab2' / 'entities.json').read_text(encoding='utf8'))['entities']
    for doc_id in IDS:
        doc = docs[doc_id]
        text = doc['clean_text']
        for match in PRON.finditer(text):
            detection_audit.append({'id': f'{doc_id}:{match.start()}', 'doc_id': doc_id,
                                    'surface': match.group(), 'start': match.start(), 'end': match.end(),
                                    'decision': 'excluded' if skip_reason(text, match.start(), match.group()) else 'candidate',
                                    'reason': skip_reason(text, match.start(), match.group()),
                                    'context': text[max(0, match.start() - 25):match.end() + 25]})
        entities = build_entities(doc_id, text, lab2)
        for row in detect(doc):
            antecedent = predict(row, text, entities)
            row['prediction'] = antecedent['text'] if antecedent else None
            row['prediction_start'] = antecedent['start'] if antecedent else None
            row['prediction_end'] = antecedent['end'] if antecedent else None
            row['prediction_type'] = antecedent['type'] if antecedent else None
            local = row['pronoun_start'] - row['sentence_start']
            row['resolved_sentence'] = (row['sentence'][:local] + row['prediction'] + row['sentence'][local + len(row['pronoun']):]
                                        if antecedent else None)
            rows.append(row)
    with (OUT / 'candidates.jsonl').open('w', encoding='utf8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    with (OUT / 'detection_audit.jsonl').open('w', encoding='utf8') as stream:
        for item in detection_audit:
            stream.write(json.dumps(item, ensure_ascii=False) + '\n')
    with (OUT / 'annotation_template.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', 'gold_antecedent', 'gold_start', 'gold_end', 'gold_type', 'status', 'note'])
        for row in rows:
            writer.writerow([row['id'], '', '', '', '', 'unreviewed', ''])
    annotations = list(csv.DictReader((OUT / 'gold.csv').open(encoding='utf-8-sig')))
    by_id = {r['id']: r for r in rows}
    evaluated = []
    for gold in annotations:
        row = by_id[gold['id']]
        doc_text = docs[row['doc_id']]['clean_text']
        if gold['status'] == 'resolved':
            assert doc_text[int(gold['gold_start']):int(gold['gold_end'])] == gold['gold_antecedent']
        if gold['status'] == 'uncertain':
            continue
        correct = (row['prediction'] == gold['gold_antecedent']) if gold['status'] == 'resolved' else row['prediction'] is None
        evaluated.append({'id': row['id'], 'pronoun': row['pronoun'], 'prediction': row['prediction'],
                          'gold': gold['gold_antecedent'] or None, 'status': gold['status'],
                          'correct': correct, 'context': row['context'], 'note': gold['note']})
    with (OUT / 'evaluation.json').open('w', encoding='utf8') as stream:
        resolvable = [x for x in evaluated if x['status'] == 'resolved']
        json.dump({'sample_size': len(evaluated), 'correct': sum(x['correct'] for x in evaluated),
                   'accuracy': sum(x['correct'] for x in evaluated) / len(evaluated),
                   'covered': sum(x['prediction'] is not None for x in evaluated),
                   'coverage': sum(x['prediction'] is not None for x in evaluated) / len(evaluated),
                   'resolvable': len(resolvable),
                   'resolvable_covered': sum(x['prediction'] is not None for x in resolvable),
                   'resolvable_coverage': sum(x['prediction'] is not None for x in resolvable) / len(resolvable),
                   'cases': evaluated}, stream, ensure_ascii=False, indent=2)
    full = []
    for item in csv.DictReader((OUT / 'full_review.csv').open(encoding='utf-8-sig')):
        row = by_id[item['id']]
        gold_text = item['gold_antecedent']
        source = docs[row['doc_id']]['clean_text']
        if gold_text:
            starts = [m.start() for m in re.finditer(re.escape(gold_text), source)]
            if item['status'] == 'cataphora':
                starts = [p for p in starts if p > row['pronoun_start']]
                gold_start = min(starts) if starts else None
            else:
                starts = [p for p in starts if p + len(gold_text) <= row['pronoun_start']]
                gold_start = max(starts) if starts else None
            assert gold_start is not None, item['id']
        else:
            gold_start = None
        full.append({'id': item['id'], 'status': item['status'], 'gold': gold_text or None,
                     'gold_start': gold_start, 'gold_end': gold_start + len(gold_text) if gold_start is not None else None,
                     'gold_type': item['gold_type'], 'prediction': row['prediction'],
                     'correct': row['prediction'] == gold_text if item['status'] == 'resolved' else
                     row['prediction'] is None if item['status'] == 'noncoref' else None,
                     'note': item['note']})
    assert len(full) == len(rows) and {x['id'] for x in full} == set(by_id)
    scored = [x for x in full if x['status'] in ('resolved', 'noncoref')]
    actual = [x for x in full if x['status'] == 'resolved']
    summary = {'candidate_count': len(full), 'status_counts': dict(Counter(x['status'] for x in full)),
               'scored_count': len(scored), 'correct': sum(x['correct'] for x in scored),
               'accuracy': sum(x['correct'] for x in scored) / len(scored),
               'resolvable_count': len(actual),
               'resolvable_covered': sum(x['prediction'] is not None for x in actual),
               'resolvable_coverage': sum(x['prediction'] is not None for x in actual) / len(actual),
               'cases': full}
    (OUT / 'full_evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'documents': len(docs), 'mentions': len(rows), 'predicted': sum(r['prediction'] is not None for r in rows), 'pronouns': Counter(r['pronoun'] for r in rows)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
