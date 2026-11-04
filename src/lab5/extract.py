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
SENT = re.compile(r'[^。！？!?；;\n.]+[。！？!?；;\n.]?')
IF = re.compile(r'如果|假如|若是|若|只要|一旦')
SUGGEST = re.compile(r'建议|最好|可以|应该|应当|尽量|不建议|不要|需要|记得|必须|可考虑|可以考虑')
ACTION = re.compile(r'建议|最好|可以|应该|应当|尽量|不建议|不要|需要|记得|必须|一定要|可考虑|可以考虑|^(?:就|则|直接|要)')
EXPLICIT = re.compile(r'(如果|假如|若是|若|只要|一旦)(?P<condition>[^，,。！？!?；;\n]{2,85}?)(?:的话)?[，,](?P<advice>[^。！？!?；;\n]{2,130})')
BECAUSE = re.compile(r'因为(?P<condition>[^，,。！？!?；;\n]{3,80})[，,](?:所以|因此)(?P<advice>[^。！？!?；;\n]{2,120})')
CONTEXT = re.compile(r'(?P<condition>(?:雨天|下雨|天晴|结冰|带老人|带孩子|有小孩|体力好|体力不好|时间有限|没有时间|时间充足|怕湿身|冬季|夏日|五月以后|带娃|带了学娃)[^，,。！？!?；;\n]{0,28})[，,](?P<advice>(?:建议|最好|可以|应该|应当|尽量|不建议|不要|需要|记得|必须|直接)[^。！？!?；;\n]{2,110})')
NO_COMMA = re.compile(r'(?:如果|假如|若是|只要|一旦)(?P<condition>[^，,。！？!?；;\n]{2,60}?)(?:的话)?(?P<advice>(?:就|则)?(?:不建议|不要|建议|可以|最好|必须|应该|应当|记得|一定要)[^，,。！？!?；;\n]{2,100})')
DUE = re.compile(r'由于(?P<condition>[^，,。！？!?；;\n]{3,65})[，,](?P<advice>(?:建议|可以|最好|应该|应当|尽量|需要)[^。！？!?；;\n]{2,100})')
SCENE = re.compile(r'(?P<condition>(?:[一二三四五六七八九十两]日游的旅客|山上风大|体力不好的人))(?P<advice>(?:建议|可以|最好|应该|应当)[^，,。！？!?；;\n]{2,90})')
ROAD = re.compile(r'(?P<condition>(?:道路|路面|山路|栈道)[^，,。！？!?；;\n]{2,24})[，,](?P<advice>(?:建议|最好|可以|应该|一定要)[^，,。！？!?；;\n]{2,90})')
CAUSE_GUIDE = re.compile(r'因为(?:考虑到)?(?P<condition>[^，,。！？!?；;\n]{3,35}?)(?:导游|领队)?(?P<advice>建议(?:乘|坐|走|带|穿|避开)[^，,。！？!?；;\n]{2,90})')
RISK = re.compile(r'(?P<condition>(?:栈道|道路|路面|阶梯)[^，,。！？!?；;\n]{3,35})[，,](?P<advice>(?:走路|行走)(?:一定要|要|最好|建议)[^，,。！？!?；;\n]{2,80})')
BARE = re.compile(r'建议|最好|可以|应该|尽量|记得')
TRIM = ' \t\r\n，,。；;：:!！?？'


def condition_type(text):
    if re.search('想走|不想走', text):
        return '路线偏好'
    if re.search('雨|雪|霜|晴|天气|结冰|雾|风|湿身|蛇|季节|冬|夏', text):
        return '天气季节'
    if re.search('老人|老年|孩子|小孩|带娃|学娃|亲子|家庭', text):
        return '游客类型'
    if re.search('体力|爬|徒步|走不动|负重|膝盖|晕车', text):
        return '体力路况'
    if re.search('时间|小时|一天|两天|两日|赶|早|晚', text):
        return '时间安排'
    if re.search('车|索道|接机|交通|出租', text):
        return '交通可达'
    return '其他显式条件'


def traveler_type(condition):
    if re.search('老人|老年', condition):
        return '老年游客'
    if re.search('孩子|小孩|带娃|学娃|娃们|亲子', condition):
        return '亲子游客'
    if re.search('体力', condition):
        return '体力约束游客'
    if '晕车' in condition:
        return '易晕车游客'
    return '普通游客'


def normalize(text):
    text = re.sub(r'[\s，,。；;：:!！?？（）()]', '', text)
    text = re.sub(r'^(?:就|则|建议|最好|可以|应当|应该|尽量|记得|可考虑|可以考虑)', '', text)
    return text


def split_advice(raw, absolute_start):
    # Split coordinated advice only when a later clause has its own action cue.
    pieces = []
    begin = 0
    for m in re.finditer(r'[,，]', raw):
        tail = raw[m.end():]
        if len(tail) > 1 and re.match(r'(?:还|也|并且|同时|另外|再)?(?:建议|最好|可以|应|要|记得|带|穿|乘|坐|避开|选择|提前)', tail):
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
                    # A later "如果" starts a separate conditional pair.
                    next_if = IF.search(a)
                    if next_if:
                        a = a[:next_if.start()].rstrip(TRIM)
                if name == 'explicit' and (c.startswith('说') or c.startswith('能有')):
                    audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'hypothetical_or_retrospective', 'fragment': hit.group()[:150]})
                    continue
                if name == 'explicit' and '建议' in c:
                    cut = c.index('建议')
                    a = c[cut:] + ',' + a
                    astart = cstart + cut
                    c = c[:cut].strip(TRIM)
                if not c or not a or not ACTION.search(a):
                    audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'no_action', 'fragment': hit.group()[:150]})
                    continue
                for advice, offset in split_advice(a, astart):
                    if len(advice) < 2:
                        continue
                    first_clause = re.split(r'[,，]', advice, maxsplit=1)[0]
                    if c in ('可以', '建议', '应该', '最好') or not ACTION.search(first_clause):
                        audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'modal_as_condition_or_late_action', 'fragment': hit.group()[:150]})
                        continue
                    if re.search(r'^(?:就|则).{0,8}(?:有可能|会)', first_clause) or first_clause.startswith('可以玩的'):
                        audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'prediction_not_advice', 'fragment': hit.group()[:150]})
                        continue
                    # A standalone mapping cannot preserve an omitted object or
                    # a deictic destination without resolving earlier discourse.
                    if (re.fullmatch(r'(?:是)?(?:反过来|放得下)', c)
                            or re.search(r'(?:不用去|先到这|以上物品)[。.!！]?$', advice)):
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
                audit.append({'doc_id': doc['doc_id'], 'sentence_start': sentence.start(), 'reason': 'offset_mismatch', 'fragment': span[:170]})
                continue
            rows.append({'id': f"{doc['doc_id']}:{cstart}:{astart}", 'doc_id': doc['doc_id'],
                         'scenic': doc['scenic'], 'text_type': doc['text_type'], 'source_name': doc['source_name'],
                         'source_record_id': doc['source_record_id'], 'source_file': doc['source_file'],
                         'source_url': doc.get('original_url') or None, 'sentence': span.strip(),
                         'sentence_start': sentence.start(), 'condition': condition, 'condition_start': cstart,
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
