"""Rule-based extraction of explicit conditional travel advice.

All offsets use clean_text (zero based, exclusive end). No inferred condition
is promoted into the final mapping without an explicit source span.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs' / 'lab5'
OUT.mkdir(parents=True, exist_ok=True)
INPUT = ROOT / 'outputs' / 'cleaned_data.jsonl'
SENT = re.compile(r'[^������!?��;\n.]+[������!?��;\n.]?')
IF = re.compile(r'���|����|����|��|ֻҪ|һ��')
SUGGEST = re.compile(r'����|���|����|Ӧ��|Ӧ��|����|������|��Ҫ|��Ҫ|�ǵ�|����|�ɿ���|���Կ���')
ACTION = re.compile(r'����|���|����|Ӧ��|Ӧ��|����|������|��Ҫ|��Ҫ|�ǵ�|����|һ��Ҫ|�ɿ���|���Կ���|^(?:��|��|ֱ��|Ҫ)')
EXPLICIT = re.compile(r'(���|����|����|��|ֻҪ|һ��)(?P<condition>[^��,������!?��;\n]{2,85}?)(?:�Ļ�)?[��,](?P<advice>[^������!?��;\n]{2,130})')
BECAUSE = re.compile(r'��Ϊ(?P<condition>[^��,������!?��;\n]{3,80})[��,](?:����|���)(?P<advice>[^������!?��;\n]{2,120})')
CONTEXT = re.compile(r'(?P<condition>(?:����|����|����|���|������|������|��С��|������|��������|ʱ������|û��ʱ��|ʱ�����|��ʪ��|����|����|�����Ժ�|����|����ѧ��)[^��,������!?��;\n]{0,28})[��,](?P<advice>(?:����|���|����|Ӧ��|Ӧ��|����|������|��Ҫ|��Ҫ|�ǵ�|����|ֱ��)[^������!?��;\n]{2,110})')
NO_COMMA = re.compile(r'(?:���|����|����|ֻҪ|һ��)(?P<condition>[^��,������!?��;\n]{2,60}?)(?:�Ļ�)?(?P<advice>(?:��|��)?(?:������|��Ҫ|����|����|���|����|Ӧ��|Ӧ��|�ǵ�|һ��Ҫ)[^��,������!?��;\n]{2,100})')
DUE = re.compile(r'����(?P<condition>[^��,������!?��;\n]{3,65})[��,](?P<advice>(?:����|����|���|Ӧ��|Ӧ��|����|��Ҫ)[^������!?��;\n]{2,100})')
SCENE = re.compile(r'(?P<condition>(?:[һ�����������߰˾�ʮ��]���ε��ÿ�|ɽ�Ϸ��|�������õ���))(?P<advice>(?:����|����|���|Ӧ��|Ӧ��)[^��,������!?��;\n]{2,90})')
ROAD = re.compile(r'(?P<condition>(?:��·|·��|ɽ·|ջ��)[^��,������!?��;\n]{2,24})[��,](?P<advice>(?:����|���|����|Ӧ��|һ��Ҫ)[^��,������!?��;\n]{2,90})')
CAUSE_GUIDE = re.compile(r'��Ϊ(?:���ǵ�)?(?P<condition>[^��,������!?��;\n]{3,35}?)(?:����|���)?(?P<advice>����(?:��|��|��|��|��|�ܿ�)[^��,������!?��;\n]{2,90})')
RISK = re.compile(r'(?P<condition>(?:ջ��|��·|·��|����)[^��,������!?��;\n]{3,35})[��,](?P<advice>(?:��·|����)(?:һ��Ҫ|Ҫ|���|����)[^��,������!?��;\n]{2,80})')
BARE = re.compile(r'����|���|����|Ӧ��|����|�ǵ�')
TRIM = ' \t\r\n��,����;��:!��?��'


def condition_type(text):
    if re.search('����|������', text):
        return '·��ƫ��'
    if re.search('��|ѩ|˪|��|����|���|��|��|ʪ��|��|����|��|��', text):
        return '��������'
    if re.search('����|����|����|С��|����|ѧ��|����|��ͥ', text):
        return '�ο�����'
    if re.search('����|��|ͽ��|�߲���|����|ϥ��|�γ�', text):
        return '����·��'
    if re.search('ʱ��|Сʱ|һ��|����|����|��|��|��', text):
        return 'ʱ�䰲��'
    if re.search('��|����|�ӻ�|��ͨ|����', text):
        return '��ͨ�ɴ�'
    return '������ʽ����'


def traveler_type(condition):
    if re.search('����|����', condition):
        return '�����ο�'
    if re.search('����|С��|����|ѧ��|����|����', condition):
        return '�����ο�'
    if re.search('����', condition):
        return '����Լ���ο�'
    if '�γ�' in condition:
        return '���γ��ο�'
    return '��ͨ�ο�'


def normalize(text):
    text = re.sub(r'[\s��,����;��:!��?������()]', '', text)
    text = re.sub(r'^(?:��|��|����|���|����|Ӧ��|Ӧ��|����|�ǵ�|�ɿ���|���Կ���)', '', text)
    return text


def split_advice(raw, absolute_start):
    # Split coordinated advice only when a later clause has its own action cue.
    pieces = []
    begin = 0
    for m in re.finditer(r'[,��]', raw):
        tail = raw[m.end():]
        if len(tail) > 1 and re.match(r'(?:��|Ҳ|����|ͬʱ|����|��)?(?:����|���|����|Ӧ|Ҫ|�ǵ�|��|��|��|��|�ܿ�|ѡ��|��ǰ)', tail):
            pieces.append((raw[begin:m.start()], absolute_start + begin))
            begin = m.end()
    pieces.append((raw[begin:], absolute_start + begin))
    return [(p.strip(TRIM), s + len(p) - len(p.lstrip(TRIM))) for p, s in pieces if p.strip(TRIM)]


def extract_doc(doc):
    text = doc['clean_text']
    rows, audit = [], []
    for sentence in SENT.finditer(text):
        span = sentence.group()
        if not (IF.search(span) or BARE.search(span) or CONTEXT.search(span)):
            continue
        candidates = []
        for priority, (name, pattern) in enumerate((('explicit', EXPLICIT), ('no_comma', NO_COMMA), ('due', DUE), ('scene', SCENE), ('because', BECAUSE), ('context', CONTEXT), ('road', ROAD), ('cause_guide', CAUSE_GUIDE), ('risk', RISK))):
            hits = list(pattern.finditer(span))
            if name == 'explicit':
                hits.extend(h for trigger in IF.finditer(span) if (h := pattern.match(span, trigger.start())) and h not in hits)
            for hit in hits:
                c = hit.group('condition').strip(TRIM)
                a = hit.group('advice').strip(TRIM)
                cstart = sentence.start() + hit.start('condition')
                astart = sentence.start() + hit.start('advice')
                if name == 'explicit':
                    # A later "���" starts a separate conditional pair.
                    next_if = IF.search(a)
                    if next_if:
                        a = a[:next_if.start()].rstrip(TRIM)
                if name == 'explicit' and (c.startswith('˵') or c.startswith('����')):
                    audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'hypothetical_or_retrospective', 'fragment': hit.group()[:150]})
                    continue
                if name == 'explicit' and '����' in c:
                    cut = c.index('����')
                    a = c[cut:] + ',' + a
                    astart = cstart + cut
                    c = c[:cut].strip(TRIM)
                if not c or not a or not ACTION.search(a):
                    audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'no_action', 'fragment': hit.group()[:150]})
                    continue
                for advice, offset in split_advice(a, astart):
                    if len(advice) < 2:
                        continue
                    first_clause = re.split(r'[,��]', advice, maxsplit=1)[0]
                    if c in ('����', '����', 'Ӧ��', '���') or not ACTION.search(first_clause):
                        audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'modal_as_condition_or_late_action', 'fragment': hit.group()[:150]})
                        continue
                    if re.search(r'^(?:��|��).{0,8}(?:�п���|��)', first_clause) or first_clause.startswith('�������'):
                        audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'prediction_not_advice', 'fragment': hit.group()[:150]})
                        continue
                    # A standalone mapping cannot preserve an omitted object or
                    # a deictic destination without resolving earlier discourse.
                    if (re.fullmatch(r'(?:��)?(?:������|�ŵ���)', c)
                            or re.search(r'(?:����ȥ|�ȵ���|������Ʒ)[��.!��]?$', advice)):
                        audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(),
                                      'reason': 'unresolved_reference', 'fragment': hit.group()[:150]})
                        continue
                    candidates.append((priority, cstart, offset, c, advice, name))
        if not candidates:
            audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'no_explicit_condition_pair', 'fragment': span[:170]})
            continue
        # Prefer explicit trigger over a nested contextual match; remove spans
        # whose advice starts at the same position inside an earlier match.
        used = set()
        for priority, cstart, astart, condition, advice, rule in sorted(candidates):
            key = (cstart, astart)
            if key in used:
                continue
            used.add(key)
            cend = cstart + len(condition)
            aend = astart + len(advice)
            if IF.search(text[cend:astart]) and rule != 'explicit':
                audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'nested_condition_changed', 'fragment': span[:170]})
                continue
            if text[cstart:cend] != condition or text[astart:aend] != advice:
                audit.append({'doc_id': doc['doc_id'], 'sentence_start': sente      'sentence_start': sentence.start(), 'condition': condition, 'condition_start': cstart,
                         'condition_end': cend, 'advice': advice, 'advice_start': astart,
                         'advice_end': aend, 'trigger': rule, 'condition_type': condition_type(condition),
                         'traveler_type': traveler_type(condition)})
    return rows, audit


def main():
    docs = [json.loads(x) for x in INPUT.read_text(encoding='utf8').splitlines() if x.strip()]
    raw, audit = [], []
    for doc in docs:
        a, b = extract_doc(doc)
        raw.extend(a)
        audit.extend(b)
    with (OUT / 'candidates.jsonl').open('w', encoding='utf8') as f:
        for r in raw:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with (OUT / 'audit.jsonl').open('w', encoding='utf8') as f:
        for r in audit:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(json.dumps({'documents': len(docs), 'raw_pairs': len(raw), 'audit': len(audit), 'by_rule': Counter(r['trigger'] for r in raw)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
