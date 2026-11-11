"""路线规划器：把图谱查询结果组装成结构化行程。

原则：
- 只用查询到的步骤与建议，不新增景点、餐厅、票价或时刻；
- 时段冲突保留两种状态，必要时用层级推断补位并写明来源；
- 两日方案是按时段切分的一日路线，不冒充官方两日线路；
- 未收录景区与信息不足走回退/追问分支，不硬凑方案。
"""
PERIOD_ORDER = ['上午', '中午', '下午', '未标注时段']


def _primary_period(step):
    """上游解析优先；没有解析值才用唯一的层级推断值。"""
    periods = step.get('periods') or []
    for p in periods:
        if p.get('status') == 'upstream_parse':
            return p['label'], p.get('status')
    if periods:
        return periods[0]['label'], periods[0].get('status')
    return '未标注时段', None


def resolve_periods(route):
    """返回 (按步骤的时段列表, 分组来源, 说明)。

    实验六的黄山、九寨沟全部步骤的上游解析时段都是“上午”，直接分组会让中午/下午为空。
    这里在“全部落在同一时段且存在层级推断值”时改用层级推断补位，并显式记录来源与冲突。
    """
    steps = route['steps']
    assignment = []
    for st in steps:
        label, status = _primary_period(st)
        assignment.append({'step': st, 'period': label, 'status': status,
                           'alternatives': [p['label'] for p in st.get('periods', [])]})
    primaries = {a['period'] for a in assignment}
    has_alt = any(len(a['step'].get('periods') or []) > 1 for a in assignment)
    source = 'upstream_parse'
    notes = []
    if len(primaries) == 1 and has_alt:
        source = 'hierarchy_heuristic_fallback'
        for a in assignment:
            for p in a['step'].get('periods') or []:
                if p.get('status') == 'conflicting_hierarchy_heuristic':
                    a['period'] = p['label']
                    a['status'] = p['status']
                    a['original_status'] = 'upstream_parse'
                    break
        notes.append('上游解析把全部步骤标为“%s”，直接分组会使中午/下午为空；'
                     '改用层级推断的时段补位，冲突状态在图中仍按两条 DURING 边保留。'
                     % next(iter(primaries)))
    elif route.get('period_conflicts'):
        notes.append('%d 个步骤同时存在上游解析与层级推断时段，行程采用上游解析值。'
                     % len(route['period_conflicts']))

    # 时序单调修复：按路线顺序取时段，若后一步时段早于前一步，沿用前一步时段，
    # 避免“上午第12步”排在下午第10/11步之后造成倒置；修复逐条记录，不静默改写。
    order = {p: i for i, p in enumerate(PERIOD_ORDER)}
    prev = None
    repaired = []
    for a in assignment:
        idx = order.get(a['period'], 3)
        if prev is not None and idx < prev:
            repaired.append({'order': a['step']['order'],
                             'spot': a['step'].get('spot') or a['step']['label'],
                             'from': a['period'], 'to': PERIOD_ORDER[prev],
                             'status': a['status']})
            a['period'] = PERIOD_ORDER[prev]
            a['status'] = 'order_monotonic_repair'
        prev = order.get(a['period'], 3)
    if repaired:
        notes.append('为避免路线顺序与时段倒置，%d 个步骤按时序单调修复（%s）。'
                     % (len(repaired), '、'.join('第%d步 %s' % (r['order'], r['spot']) for r in repaired)))
    return assignment, source, ' '.join(notes), repaired


def _sections(assignment):
    buckets = {p: [] for p in PERIOD_ORDER}
    for a in assignment:
        st = a['step']
        spot = st.get('spot') or (st.get('transports') or [{}])[0].get('label') or st['label']
        buckets.setdefault(a['period'], []).append({
            'order': st['order'], 'step_id': st['step_id'], 'spot': spot,
            'activity': st.get('activity'), 'period': a['period'],
            'period_status': a['status'], 'period_alternatives': a['alternatives'],
            'evidence_refs': st.get('evidence_refs') or [],
        })
    return [{'period': p, 'steps': buckets.get(p, [])} for p in PERIOD_ORDER if buckets.get(p)]


def _duplicate_notes(assignment):
    seen, dup = {}, []
    for a in assignment:
        spot = a['step'].get('spot') or a['step']['label']
        if spot in seen:
            dup.append('%s 在第 %d 与第 %d 步重复出现，按实验六“身份去重、步骤不去重”保留两次。'
                       % (spot, seen[spot], a['step']['order']))
        else:
            seen[spot] = a['step']['order']
    return dup


def choose_scenic(scenics, intent):
    """未指定景区时的确定性择优：人群相关建议覆盖 > 通用建议 > 步骤数。

    这是代理指标，只说明图谱里哪条路线与该人群的条件建议更接近，
    不代表真实适配已经验证。评分明细写入 plan['selection']。
    """
    visitor = intent['visitor_type']
    rows = []
    for s in scenics:
        score = s['condition_count'] * 10 + s['step_count']
        rows.append({'scenic': s['scenic'], 'condition_count': s['condition_count'],
                     'step_count': s['step_count'], 'score': score})
    rows.sort(key=lambda r: (-r['score'], -r['step_count'], r['scenic']))
    return rows[0]['scenic'], rows, (
        '未指定景区：按“条件建议条数(×10) + 路线步骤数”排序，选 %s；'
        '这是图谱覆盖度的代理指标，不是适配验证。' % rows[0]['scenic'])


def _advice_view(advice_obs):
    if not advice_obs or not advice_obs.get('ok'):
        return []
    out = []
    for a in advice_obs.get('advices', []):
        out.append({'condition': a['condition'], 'advice': a['advice'],
                    'traveler_type': a['traveler_type'], 'condition_type': a['condition_type'],
                    'negative': a['negative'], 'historical_only': a['historical_only'],
                    'mapping_id': a['mapping_id'], 'evidence_refs': a['evidence_refs']})
    return out


def build(intent, observations, llm):
    """observations: {scenics, route, advice}，每个是对应工具返回。"""
    base = {
        'scenic': intent['scenic'], 'visitor_type': intent['visitor_type'],
        'duration': intent['duration'], 'preferences': intent['preferences'],
        'constraints': intent['constraints'], 'days': [], 'advices': [],
        'warnings': [], 'notes': [], 'period_note': '', 'selection': None,
        'evidence_ids': [], 'found': None,
    }
    if intent.get('need_clarification'):
        base['need_clarification'] = True
        base['found'] = False
        base['clarify_message'] = next((f for f in intent['flags'] if '请补充' in f), None) \
            or '请补充景区、人群与天数后再规划。'
        base['summary'] = llm.compose(base)
        return base

    scenics_obs = observations.get('scenics')
    if intent.get('unknown_scenic'):
        options = scenics_obs['available'] if scenics_obs else []
        base['found'] = False
        base['scenic'] = None
        base['message'] = ('知识图谱暂未收录「%s」。当前可规划景区：%s。'
                           '未用其他景区数据替代，也未编造该景区路线。'
                           % (intent['unknown_scenic'], '、'.join(options)))
        base['summary'] = llm.compose(base)
        return base
    if not intent['scenic'] and scenics_obs:
        picked, rows, reason = choose_scenic(scenics_obs['scenics'], intent)
        base['scenic'] = picked
        base['selection'] = {'ranking': rows, 'reason': reason}
        base['notes'].append(reason)
    if not base['scenic']:
        base['found'] = False
        base['need_clarification'] = True
        base['clarify_message'] = '请补充想去的景区、同行人群与天数。'
        base['summary'] = llm.compose(base)
        return base

    route = observations.get('route')
    if not route or not route.get('ok') or not route.get('found'):
        base['found'] = False
        base['message'] = '图谱中未找到“%s”的路线。' % base['scenic']
        base['summary'] = llm.compose(base)
        return base

    base['found'] = True
    base['route_meta'] = {'route_id': route['route_id'], 'route_label': route['route_label'],
                          'step_count': route['step_count']}
    assignment, source, period_note, repaired = resolve_periods(route)
    base['period_source'] = source
    base['period_note'] = period_note
    base['period_repairs'] = repaired
    sections = _sections(assignment)
    base['warnings'] += [w for w in intent['flags']]

    if intent['duration'] == 2:
        am = [s for s in sections if s['period'] == '上午']
        rest = [s for s in sections if s['period'] != '上午']
        if am and rest:
            base['days'] = [{'day': 1, 'sections': am}, {'day': 2, 'sections': rest}]
        else:
            flat = [st for sec in sections for st in sec['steps']]
            half = max(1, len(flat) // 2)
            base['days'] = [
                {'day': 1, 'sections': [{'period': '第1天', 'steps': flat[:half]}]},
                {'day': 2, 'sections': [{'period': '第2天', 'steps': flat[half:]}]},
            ]
        base['warnings'].append('两日方案是按图谱时段/步骤切分的一日路线，不是官方两日线路；'
                                '住宿与第二天交通未被图谱收录，未做安排。')
    else:
        base['days'] = [{'day': 1, 'sections': sections}]

    base['advices'] = _advice_view(observations.get('advice'))
    if observations.get('advice') and observations['advice'].get('fallback_note'):
        base['notes'].append('建议回退：' + observations['advice']['fallback_note'])
    if '易晕车' in intent['constraints'] and any('晕车' in a['condition'] for a in base['advices']):
        base['notes'].append('已按“晕车”约束取出图谱中的晕车相关建议；该建议来自游客叙述，需自行核验。')

    dups = _duplicate_notes(assignment)
    base['notes'] += dups
    if intent['constraints'] and '体力:高强度' in intent['constraints']:
        base['warnings'].append('请求含爬山/徒步等高强度约束；图谱只能沿原路线顺序给出景点，'
                                '不能评估坡度与体力消耗，需另行核验。')
    if any('午后上山' in a['advice'] for a in base['advices']) and intent['duration'] == 2 \
            and base['days'][0]['sections'][0]['period'] == '上午':
        base['warnings'].append('图谱中的“两日游建议午后上山”与本次按上午起点的切分不一致，'
                                '两种做法都保留，未擅自改序。')
    if intent['duration'] == 1:
        base['notes'].append('图谱未收录餐饮与休息设施，中午不编造具体餐厅，只在时段上留出休整。')
    if intent['visitor_type'] == '老人':
        base['warnings'].append('图谱未收录坡度、海拔与点间距离，老人同行的体力消耗无法评估；'
                                '建议优先参考图谱中的索道/乘车类建议，并以景区当前公告为准。')

    cited = set()
    for day in base['days']:
        for sec in day['sections']:
            for st in sec['steps']:
                cited.update(st['evidence_refs'])
    for a in base['advices']:
        cited.update(a['evidence_refs'])
    base['evidence_ids'] = sorted(cited)
    # 同一提示可能同时来自意图层与规划层，去重但保持出现顺序
    base['warnings'] = list(dict.fromkeys(base['warnings']))
    base['notes'] = list(dict.fromkeys(base['notes']))
    base['summary'] = llm.compose(base)
    return base
