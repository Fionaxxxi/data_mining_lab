"""意图解析器：把用户自然语言请求解析成显式约束。

规则版（offline）与 LLM 版共用同一输出结构：
{raw, scenic, unknown_scenic, visitor_type, duration, preferences, constraints,
 need_clarification, flags, matched_rules}
LLM 可用时由 llm.py 生成 JSON 再与本模块的结构校验；不可用时完全走规则版，
不把规则结果伪装成模型输出。
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / 'data/lab7/agent_rules.json'

VISITOR_ORDER = ['亲子', '老人', '情侣']


def load_rules(path=RULES_PATH):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def empty_intent(raw):
    return {
        'raw': raw, 'scenic': None, 'unknown_scenic': None, 'visitor_type': '普通',
        'duration': 1, 'duration_explicit': False, 'preferences': [], 'constraints': [],
        'need_clarification': False, 'flags': [], 'matched_rules': [],
    }


def _find_scenic(text, rules):
    hits = []
    for scenic, aliases in rules['scenic_aliases'].items():
        for a in aliases:
            if a in text:
                hits.append((len(a), scenic, a))
    if not hits:
        return None, None
    hits.sort(reverse=True)
    return hits[0][1], hits[0][2]


def _find_unknown_scenic(text, rules, scenic):
    if scenic:
        return None, None
    for name in rules['other_scenics']:
        if name in text:
            return name, 'known_other_scenic_list'
    m = re.search(rules['generic_scenic_pattern'], text)
    if m:
        cand = m.group(1)
        if cand in rules['generic_scenic_blacklist']:
            return None, None
        if any(w in cand for w in rules['generic_scenic_blacklist']):
            return None, None
        return cand, 'generic_place_suffix'
    return None, None


def _find_visitor(text, rules):
    found = []
    for vt, kws in rules['visitor_keywords'].items():
        for k in kws:
            if k in text:
                found.append((k, vt))
    if not found:
        return '普通', None
    # 亲子优先于老人，避免“带老人和孩子”被老人覆盖掉亲子设施需求
    for vt in VISITOR_ORDER:
        for k, v in found:
            if v == vt:
                return vt, k
    return found[0][1], found[0][0]


def _find_duration(text, rules):
    for days in ('2', '1'):
        for k in rules['duration_keywords'][days]:
            if k in text:
                return int(days), k
    return 1, None


def _find_preferences(text, rules):
    prefs, hits = [], []
    for p, kws in rules['preference_keywords'].items():
        for k in kws:
            if k in text:
                prefs.append(p)
                hits.append('%s<-%s' % (p, k))
                break
    return prefs, hits


def _find_constraints(text, rules):
    cons, hits = [], []
    for c, kws in rules['constraint_keywords'].items():
        for k in kws:
            if k in text:
                cons.append(c)
                hits.append('%s<-%s' % (c, k))
                break
    return cons, hits


def parse(raw, rules=None):
    """规则版解析；输出固定结构，供 Agent 与 LLM 兜底共用。"""
    rules = rules or load_rules()
    text = re.sub(r'\s+', ' ', raw or '').strip()
    it = empty_intent(raw)
    if not text:
        it['need_clarification'] = True
        it['flags'].append('输入为空，需追问景区、人群与天数。')
        return it

    scenic, alias = _find_scenic(text, rules)
    it['scenic'] = scenic
    if alias:
        it['matched_rules'].append('scenic:%s<-%s' % (scenic, alias))

    unknown, rule = _find_unknown_scenic(text, rules, scenic)
    it['unknown_scenic'] = unknown
    if unknown:
        it['matched_rules'].append('unknown_scenic:%s<-%s' % (unknown, rule))

    vt, kw = _find_visitor(text, rules)
    it['visitor_type'] = vt
    if kw:
        it['matched_rules'].append('visitor:%s<-%s' % (vt, kw))

    days, kw = _find_duration(text, rules)
    it['duration'] = days
    it['duration_explicit'] = kw is not None
    if kw:
        it['matched_rules'].append('duration:%d<-%s' % (days, kw))

    prefs, phits = _find_preferences(text, rules)
    it['preferences'] = prefs
    it['matched_rules'] += ['preference:' + h for h in phits]

    cons, chits = _find_constraints(text, rules)
    it['constraints'] = cons
    it['matched_rules'] += ['constraint:' + h for h in chits]

    for r in rules['conflict_rules']:
        cond = r['when']
        if cond.get('visitor') == it['visitor_type'] and cond.get('constraint') in cons:
            it['flags'].append(r['message'])
            it['matched_rules'].append('conflict:' + r['id'])

    if not scenic and not unknown:
        it['flags'].append('未指定景区；可选 ' + '、'.join(sorted(rules['scenic_aliases'])) + '。')
    if not it['duration_explicit']:
        it['flags'].append('未说明天数，默认按 1 天规划。')
    if days == 2:
        it['flags'].append('实验六图谱为一日官方整理路线；两日方案按时段切分，并非官方两日线路。')
    if unknown:
        it['flags'].append('「%s」不在实验六图谱收录范围，将如实说明并给出可选景区。' % unknown)

    # 信息不足：既没景区也没人群/偏好/明确天数，向用户追问而不是盲猜
    if not scenic and not unknown and vt == '普通' and not prefs and not cons and not it['duration_explicit']:
        it['need_clarification'] = True
        it['flags'].append(rules['clarify_question'])
    return it
