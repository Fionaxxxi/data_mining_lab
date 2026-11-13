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


def _apply_llm_plan(base, intent, llm, query):
    """Ask the model to plan within graph steps, then reject any altered route facts."""
    if not getattr(llm, 'online', False):
        return
    failures_before = llm.failures
    try:
        proposal = llm.plan_itinerary(query, base)
        if not isinstance(proposal, dict):
            raise ValueError('规划提案必须是 JSON 对象')
        original = []
        period_by_order = {}
        step_by_order = {}
        for day in base.get('days', []):
            for section in day.get('sections', []):
                for step in section.get('steps', []):
                    order = step.get('order')
                    if isinstance(order, bool) or not isinstance(order, int) or order in step_by_order:
                        raise ValueError('图谱计划中的步骤序号无效或重复')
                    original.append(order)
                    period_by_order[order] = section['period']
                    step_by_order[order] = step

        assignments = proposal.get('day_assignments')
        if not isinstance(assignments, list) or len(assignments) != len(original):
            raise ValueError('day_assignments 必须覆盖全部图谱步骤')
        assigned_orders, day_numbers = [], []
        for item in assignments:
            if not isinstance(item, dict):
                raise ValueError('day_assignments 每项必须是对象')
            order, day = item.get('order'), item.get('day')
            if isinstance(order, bool) or not isinstance(order, int) \
                    or isinstance(day, bool) or not isinstance(day, int):
                raise ValueError('步骤序号和天数必须是整数')
            assigned_orders.append(order)
            day_numbers.append(day)
        if assigned_orders != original:
            raise ValueError('规划提案改动、遗漏、重复或重排了图谱步骤')
        duration = int(intent['duration'])
        if any(day < 1 or day > duration for day in day_numbers):
            raise ValueError('规划提案天数超出用户计划')
        if day_numbers != sorted(day_numbers) or set(day_numbers) != set(range(1, duration + 1)):
            raise ValueError('分日必须按路线顺序连续且每天有步骤')
        pace = proposal.get('pace')
        if pace not in {'轻松', '适中', '紧凑'}:
            raise ValueError('pace 必须为轻松/适中/紧凑')
        rationale = proposal.get('rationale')
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 160:
            raise ValueError('rationale 必须为 1–160 字的规划说明')
        if intent.get('visitor_type') == '老人' and pace != '轻松':
            raise ValueError('老人同行的节奏必须标为轻松')

        day_by_order = dict(zip(assigned_orders, day_numbers))
        planned_days = []
        for day_no in range(1, duration + 1):
            sections = []
            for order in original:
                if day_by_order[order] != day_no:
                    continue
                period = period_by_order[order]
                if not sections or sections[-1]['period'] != period:
                    sections.append({'period': period, 'steps': []})
                sections[-1]['steps'].append(step_by_order[order])
            planned_days.append({'day': day_no, 'sections': sections})
        base['days'] = planned_days
        base['llm_planning'] = {
            'status': 'accepted', 'pace': pace,
            'day_assignments': assignments, 'rationale': rationale.strip(),
        }
        llm.accept_planning()
    except Exception as ex:
        llm.record_fallback(ex, failure_already_recorded=llm.failures > failures_before,
                            stage='planning')
        base['llm_planning'] = {'status': 'rejected', 'error': llm.last_error}
        base['notes'].append('LLM 规划提案未通过图谱步骤与用户约束校验，已使用规则计划。')


def build(intent, observations, llm, query=''):
    """observations: {scenics, route, advice}，每个是对应工具返回。"""
    base = {
        'scenic': intent['scenic'], 'visitor_type': intent['visitor_type'],
        'duration': intent['duration'], 'preferences': intent['preferences'],
        'constraints': intent['constraints'], 'days': [], 'advices': [],
        'warnings': [], 'notes': [], 'period_note': '', 'selection': None,
        'evidence_ids': [], 'found': None, 'query': query,
        'task_type': intent.get('task_type', 'route'), 'answer_context': {},
    }
    if intent.get('need_clarification'):
        base['need_clarification'] = True
        base['found'] = False
        base['clarify_message'] = next((f for f in intent['flags'] if '请补充' in f), None) \
            or '请补充景区、人群与天数后再规划。'
        base['summary'] = llm.compose(base)
        return base

    if base['task_type'] == 'entity':
        entity = observations.get('entity')
        base['answer_type'] = 'entity'
        base['answer_context'] = entity or {}
        if not intent.get('scenic') or not intent.get('entity_name'):
            base['need_clarification'] = True
            base['found'] = False
            base['clarify_message'] = '请补充实体所在景区和要查询的地点名称。'
            base['summary'] = llm.compose(base)
            return base
        if not entity or not entity.get('ok'):
            base['found'] = False
            base['message'] = '图谱实体查询未能完成。'
        else:
            base['found'] = bool(entity.get('found'))
            matches = entity.get('matches') or []
            base['evidence_ids'] = sorted({ref for item in matches for ref in item.get('evidence_refs', [])})
            if not base['found']:
                base['message'] = '圖譜中未找到「%s」的精確實體記錄；相似名稱僅供人工確認，不作同義結論。' % entity.get('name', '')
        base['summary'] = llm.compose(base)
        return base

    if base['task_type'] == 'advice':
        advice = observations.get('advice')
        base['answer_type'] = 'advice'
        base['answer_context'] = advice or {}
        if not advice or not advice.get('ok') or not advice.get('found'):
            base['found'] = False
            base['message'] = '图谱中未找到该景区的相关建议。'
        else:
            base['found'] = True
            base['advices'] = _advice_view(advice)
            base['evidence_ids'] = sorted({ref for item in base['advices'] for ref in item.get('evidence_refs', [])})
            if advice.get('fallback_note'):
                base['notes'].append(advice['fallback_note'])
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

    if base['task_type'] == 'general':
        scenics = observations.get('scenics') or {}
        base['answer_type'] = 'general'
        base['answer_context'] = scenics
        base['found'] = bool(scenics.get('ok'))
        names = scenics.get('available') or []
        base['message'] = '当前图谱收录景区：%s。' % '、'.join(names) if names else '图谱景区清单暂不可用。'
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
    _apply_llm_plan(base, intent, llm, query)
    base['summary'] = llm.compose(base)
    return base
