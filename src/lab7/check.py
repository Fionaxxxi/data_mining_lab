"""验收检查：结构、证据、回退行为与可复现性。

不只检查“程序能跑完”，还核对：
- 方案里的景点必须回指实验六图谱步骤，步骤再回指实验二/三证据；
- 引用的 evidence id 必须存在于实验六 evidence.jsonl，并统计其上游来源文件；
- 未收录景区、信息不足、工具非法参数等边界行为是否按约定收敛；
- 同一离线输入重复运行是否得到相同方案。
"""
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agent import ReActAgent  # noqa: E402
from graph_tool import KGQueryTool  # noqa: E402
from llm import LLMClient  # noqa: E402

ROOT = HERE.parents[1]
DATA = ROOT / 'data/lab7'
OUT = ROOT / 'outputs/lab7'
UPSTREAM = {
    'outputs/lab3/structured_routes.json': '实验三 路线步骤',
    'outputs/lab2/entities.json': '实验二 实体提及',
    'outputs/lab5/mapping.json': '实验五 条件建议',
    'outputs/lab4/candidates.jsonl': '实验四 共指证据',
    'outputs/lab3/time_hierarchy.json': '实验三 时间层级',
}

FORBIDDEN_CLAIMS = ['票价', '门票', '营业时间', '现在开放', '必去', '唯一选择']


def main():
    checks = []

    def check(cid, passed, detail):
        checks.append({'id': cid, 'passed': bool(passed), 'detail': detail})

    meta = json.loads((OUT / 'meta.json').read_text(encoding='utf-8'))
    cases = json.loads((OUT / 'test_cases.json').read_text(encoding='utf-8'))
    traces = [json.loads(x) for x in (OUT / 'traces.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]

    # 1 图谱来源与哈希
    tool = KGQueryTool()
    sha = tool.sha256
    check('graph_sha_matches_meta', sha == meta['graph_sha256'],
          'graph.json sha256=%s… 与 meta 记录%s' % (sha[:16], '一致' if sha == meta['graph_sha256'] else '不一致'))
    stats = json.loads((ROOT / 'outputs/lab6/stats.json').read_text(encoding='utf-8'))
    check('graph_scale_from_lab6', len(tool.nodes) == stats['nodes'] and len(tool.edges) == stats['edges'],
          '节点 %d/%d，边 %d/%d（实验六 stats）' % (len(tool.nodes), stats['nodes'], len(tool.edges), stats['edges']))

    # 2 场景数量与覆盖
    tags = {c['tag'] for c in cases}
    check('scenario_count', len(cases) == meta['scenario_count'] == 8, '实际 %d 例' % len(cases))
    check('scenario_diversity', len({'老人', '亲子', '情侣'} & {c['intent']['visitor_type'] for c in cases}) == 3,
          '覆盖游客类型：' + '、'.join(sorted({c['intent']['visitor_type'] for c in cases})))
    check('two_day_covered', any(c['intent']['duration'] == 2 for c in cases), '两日场景存在')

    # 3 方案景点必须来自图谱路线
    bad_steps, bad_refs, citations = [], [], []
    for c in cases:
        if not c['found']:
            continue
        route = tool.run({'action': 'route', 'scenic': c['scenic']})
        step_ids = {s['step_id']: s for s in route['steps']}
        for day in c['days']:
            for sec in day['sections']:
                for s in sec['steps']:
                    sid = None
                    for k, v in step_ids.items():
                        if v['order'] == int(s.split()[0]):
                            sid = k
                    if sid is None:
                        bad_steps.append((c['id'], s))
                    else:
                        citations += step_ids[sid]['evidence_refs']
        citations += c.get('evidence_ids', [])
    check('plan_spots_traceable_to_lab6_steps', not bad_steps,
          '越界步骤 %d 个' % len(bad_steps))

    # 4 每条引用都可在实验六证据表解析，并统计上游来源
    ev = {}
    for line in (ROOT / 'outputs/lab6/evidence.jsonl').read_text(encoding='utf8').splitlines():
        if line.strip():
            r = json.loads(line)
            ev[r['id']] = r
    missing = sorted({i for i in citations if i not in ev})
    check('all_evidence_ids_resolve', not missing,
          '引用 %d 条，缺失 %d 条' % (len(set(citations)), len(missing)))
    files = {}
    for i in set(citations):
        if i in ev:
            files[ev[i]['file']] = files.get(ev[i]['file'], 0) + 1
    upstream_hit = [f for f in files if f in UPSTREAM]
    check('multi_lab_provenance', len(upstream_hit) >= 2,
          '证据来自 %d 个上游文件：%s' % (len(files), '；'.join('%s(%d)' % (f, n) for f, n in sorted(files.items()))))

    # 5 建议均为历史建议，且逐条带出处
    advice_rows = [a for c in cases for a in c['advices']]
    check('advices_historical_and_referenced',
          bool(advice_rows) and all(a['historical_only'] and a['evidence_refs'] for a in advice_rows),
          '建议 %d 条，全部 historical_only 且有 evidence_refs' % len(advice_rows))
    per_case_dups = []
    for c in cases:
        ids = [a['mapping_id'] for a in c['advices']]
        if len(ids) != len(set(ids)):
            per_case_dups.append(c['id'])
    check('advice_mapping_ids_unique_per_case', not per_case_dups,
          '同一方案内重复 mapping_id 的场景：%s' % (per_case_dups or '无'))

    # 6 边界行为
    unknown = next(c for c in cases if c['id'] == 'unknown_taishan')
    check('unknown_scenic_no_fabrication',
          unknown['found'] is False and unknown['scenic'] is None and unknown['step_count'] == 0
          and '未收录' in (unknown['message'] or ''),
          '未收录场景：found=%s scenic=%s steps=%d' % (unknown['found'], unknown['scenic'], unknown['step_count']))
    vague = next(c for c in cases if c['id'] == 'vague_request')
    check('vague_request_clarifies', vague['need_clarification'] and vague['tool_call_count'] == 0,
          '信息不足：追问=%s 工具调用=%d' % (vague['need_clarification'], vague['tool_call_count']))

    # 7 工具 schema 与异常兜底
    bad_action = tool.run({'action': 'plan', 'scenic': '黄山'})
    missing_scenic = tool.run({'action': 'route'})
    extra_arg = tool.run({'action': 'scenics', 'scenic': '黄山'})
    bad_entity = tool.run({'action': 'entity', 'scenic': '黄山'})
    check('tool_rejects_unknown_action', bad_action['ok'] is False, bad_action.get('error'))
    check('tool_requires_scenic', missing_scenic['ok'] is False, missing_scenic.get('error'))
    check('tool_rejects_extra_args', extra_arg['ok'] is False, extra_arg.get('error'))
    check('tool_entity_requires_name', bad_entity['ok'] is False, bad_entity.get('error'))
    empty = tool.run({'action': 'route', 'scenic': '泰山'})
    check('tool_unknown_scenic_empty', empty['ok'] is True and empty['found'] is False
          and empty.get('available') == ['九寨沟', '张家界', '黄山'],
          '返回 found=%s，可选 %s' % (empty.get('found'), empty.get('available')))
    fallback = tool.run({'action': 'advice', 'scenic': '九寨沟', 'traveler_type': '亲子'})
    check('advice_fallback_annotated', bool(fallback.get('fallback_note')),
          '无对应游客类型时 fallback_note=%r' % (fallback.get('fallback_note'),))

    # 8 轨迹完整性
    trace_by_id = {t['id']: t['traces'] for t in traces}
    check('trace_one_per_case', len(traces) == len(cases), '轨迹 %d 条 / 场景 %d 例' % (len(traces), len(cases)))
    bad_trace = []
    for c in cases:
        tr = trace_by_id.get(c['id'], [])
        types = [t['type'] for t in tr]
        if 'final' not in types:
            bad_trace.append((c['id'], '缺 final'))
        if c['tool_call_count'] and not ('action' in types and 'observation' in types):
            bad_trace.append((c['id'], '有工具调用但缺 action/observation'))
        if c['tool_call_count'] > 6:
            bad_trace.append((c['id'], '超过 6 次工具调用'))
    check('react_trace_complete', not bad_trace, '问题：%s' % (bad_trace or '无'))
    check('max_tool_calls_bounded', max(c['tool_call_count'] for c in cases) <= 6,
          '最大调用 %d 次' % max(c['tool_call_count'] for c in cases))

    # 9 时段状态只允许约定枚举，且修复可追溯
    allowed_status = {'upstream_parse', 'conflicting_hierarchy_heuristic', 'order_monotonic_repair'}
    statuses, repaired = set(), 0
    for c in cases:
        for day in c['days']:
            for sec in day['sections']:
                for s in sec['steps']:
                    m = re.search(r'\(([^()]+)\)$', s)
                    statuses.add(m.group(1) if m else 'UNPARSED')
        repaired += len(c.get('period_repairs') or [])
    check('period_status_enumerated', statuses <= allowed_status, '实际状态 %s' % sorted(statuses))
    check('period_repairs_recorded', repaired >= 1, '记录修复 %d 处' % repaired)

    # 10 禁止越权断言（“门票站”是图谱地点名，先剔除再扫描）
    text = ' '.join((c['summary'] or '') for c in cases).replace('门票站', '')
    hits = [w for w in FORBIDDEN_CLAIMS if w in text]
    check('no_fabricated_current_status', not hits, '命中越权词：%s' % (hits or '无'))
    check('uncertainty_disclosed', '未核验' in text, '方案是否声明未核验通行/开放')

    # 11 可复现：同一离线输入两次运行一致
    agent = ReActAgent(tool=KGQueryTool(), llm=LLMClient(force_offline=True))
    r1 = agent.run('带老人去黄山玩一天，希望行程轻松平缓')
    r2 = ReActAgent(tool=KGQueryTool(), llm=LLMClient(force_offline=True)).run('带老人去黄山玩一天，希望行程轻松平缓')
    same = json.dumps(r1['plan']['days'], ensure_ascii=False) == json.dumps(r2['plan']['days'], ensure_ascii=False) \
        and r1['plan']['summary'] == r2['plan']['summary']
    check('deterministic_offline', same, '两次运行的 days 与 summary %s' % ('一致' if same else '不一致'))
    check('provider_offline_when_forced', r1['provider'] == 'offline-rules'
          and r1['llm']['request_attempts'] == 0,
          'provider=%s，HTTP 请求=%d' % (r1['provider'], r1['llm']['request_attempts']))

    # 12 图件存在；SVG 可直接插入报告，也不依赖本机 matplotlib 重绘。
    figs = ['agent_architecture.svg', 'react_trace_demo.svg', 'plan_timeline.svg']
    fig_ok = all((OUT / 'figures' / f).exists() and (OUT / 'figures' / f).stat().st_size > 8000 for f in figs)
    check('figures_present', fig_ok, '检查 %s' % '、'.join(figs))

    # 13 在线调用链用本地假响应验证，不把它冒充真实 API 连通性。
    import os
    from unittest.mock import patch
    import llm as llm_mod
    calls = []
    def fake_post(url, payload, headers, timeout):
        calls.append({'url': url, 'payload': payload, 'headers': headers})
        if len(calls) == 1:
            # 故意给出与用户明确请求冲突的景区，验证规则约束不能被模型覆盖。
            content = json.dumps({'scenic': '张家界', 'visitor_type': '情侣', 'duration': 2,
                                  'preferences': [], 'constraints': [], 'need_clarification': False})
        elif len(calls) == 2:
            content = json.dumps({'action': 'route', 'args': {'scenic': '黄山'},
                                  'reason': '明确询问黄山行程，先查图谱路线。'}, ensure_ascii=False)
        elif len(calls) == 3:
            content = json.dumps({'action': 'advice', 'args': {'scenic': '黄山',
                                  'traveler_type': '老人', 'limit': 6},
                                  'reason': '老人同行，再查体力相关历史建议。'}, ensure_ascii=False)
        elif len(calls) == 4:
            content = json.dumps({
                'day_assignments': [{'order': i, 'day': 1} for i in range(1, 15)],
                'pace': '轻松', 'rationale': '按老人同行和轻松偏好安排一天，沿用图谱步骤。'
            }, ensure_ascii=False)
        else:
            content = '黄山一日行程：南大门出发；建议参考图谱历史建议乘索道。以上景点均来自图谱，实际通行未核验。'
        return {'choices': [{'message': {'content': content}}]}
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'local-test-key',
                                 'OPENAI_BASE_URL': 'https://mock.invalid/v1',
                                 'OPENAI_MODEL': 'mock-model'}), patch.object(llm_mod, '_post_json', fake_post):
        simulated = ReActAgent(tool=tool, llm=LLMClient()).run('带老人去黄山玩一天')
    online_ok = len(calls) == 5 and simulated['intent']['scenic'] == '黄山' \
        and simulated['intent']['visitor_type'] == '老人' and simulated['intent']['duration'] == 1 \
        and simulated['plan']['scenic'] == '黄山' and simulated['plan']['found'] \
        and simulated['llm']['request_attempts'] == 5 \
        and simulated['llm']['successful_responses'] == 5 \
        and simulated['llm']['decision_attempts'] == 2 \
        and simulated['llm']['decision_accepted'] == 2 \
        and [c['action'] for c in simulated['tool_calls']] == ['route', 'advice'] \
        and simulated['plan']['llm_planning']['status'] == 'accepted' \
        and simulated['llm']['planning_accepted'] == 1 \
        and simulated['plan']['summary'] == '黄山一日行程：南大门出发；建议参考图谱历史建议乘索道。以上景点均来自图谱，实际通行未核验。' \
        and calls[0]['url'] == 'https://mock.invalid/v1/chat/completions' \
        and calls[0]['headers'].get('Authorization') == 'Bearer local-test-key'
    check('llm_mock_input_output_chain', online_ok,
          '本地模拟调用 %d 次；明确景区保留为 %s；未测试真实外部 API' %
          (len(calls), simulated['plan']['scenic']))
    decision_prompt = calls[2]['payload']['messages'][1]['content']
    check('llm_decision_uses_tool_observation', '"step_count": 14' in decision_prompt
          and 'route' in decision_prompt,
          '第二轮工具决策输入包含第一轮路线 Observation')
    decision_traces = [t for t in simulated['traces'] if t.get('decision_source')]
    check('llm_decision_trace_records_action', len(decision_traces) == 2
          and all(t['decision_source'] == 'llm' for t in decision_traces)
          and [t.get('decision') for t in decision_traces] == ['route', 'advice'],
          'Thought 轨迹记录真实 LLM 的路线和建议选择')
    check('llm_action_observations_reach_final', '南大门' in simulated['plan']['summary']
          and '乘索道' in simulated['plan']['summary']
          and bool(simulated['plan']['evidence_ids']),
          '最终答复复用图谱路线点、查询建议和 evidence ID')
    request_ok = len(calls) == 5 and all(
        c['url'] == 'https://mock.invalid/v1/chat/completions'
        and c['payload'].get('model') == 'mock-model'
        and c['headers'].get('Authorization') == 'Bearer local-test-key'
        for c in calls) and 'local-test-key' not in json.dumps(simulated, ensure_ascii=False)
    check('llm_mock_request_contract', request_ok,
          '检查 URL、模型名和 Bearer 头，不输出密钥')
    locked = simulated['intent']['scenic'] == '黄山' \
        and simulated['intent']['visitor_type'] == '老人' \
        and simulated['intent']['duration'] == 1 \
        and simulated['plan']['scenic'] == '黄山'
    check('llm_explicit_constraints_locked', locked,
          '冲突模拟响应未覆盖用户明确给出的黄山、老人、一日')

    from intent import parse as parse_intent
    classified = {
        'route': parse_intent('带老人去黄山玩一天').get('task_type'),
        'advice': parse_intent('黄山有哪些老人出行建议？').get('task_type'),
        'entity': parse_intent('黄山迎客松被提及几次？').get('task_type'),
        'general': parse_intent('图谱收录了哪些景区？').get('task_type'),
    }
    check('intent_classifies_four_query_types', classified == {
        'route': 'route', 'advice': 'advice', 'entity': 'entity', 'general': 'general'},
        '路线/建议/实体/收录范围分类：%s' % classified)

    validator = ReActAgent(tool=tool, llm=LLMClient(force_offline=True))
    route_state = {'intent': parse_intent('带老人去黄山玩一天'), 'obs': {}}
    unsafe_rejected = False
    premature_rejected = False
    try:
        validator._validate_action_decision({'action': 'route', 'args': {'scenic': '张家界'},
                                             'reason': '改换景区'}, route_state, '带老人去黄山玩一天')
    except ValueError:
        unsafe_rejected = True
    try:
        validator._validate_action_decision({'action': 'stop', 'args': {}, 'reason': '提前结束'},
                                             route_state, '带老人去黄山玩一天')
    except ValueError:
        premature_rejected = True
    check('llm_decision_enforces_user_constraints', unsafe_rejected and premature_rejected,
          '拒绝改写用户景区及缺少路线结果时提前 stop')

    def run_mocked_query(query, script):
        mock_calls = []
        def respond(url, payload, headers, timeout):
            mock_calls.append(payload)
            item = script[len(mock_calls) - 1]
            content = item(payload) if callable(item) else item
            return {'choices': [{'message': {'content': content}}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'local-test-key',
                                     'OPENAI_BASE_URL': 'https://mock.invalid/v1',
                                     'OPENAI_MODEL': 'mock-model'}), patch.object(llm_mod, '_post_json', respond):
            output = ReActAgent(tool=tool, llm=LLMClient()).run(query)
        return output, mock_calls

    entity_query = '黄山迎客松被提及次数是多少？'
    entity_intent = json.dumps({'scenic': '黄山', 'unknown_scenic': '', 'visitor_type': '普通',
                                'duration': 1, 'preferences': [], 'constraints': [],
                                'need_clarification': False, 'task_type': 'entity',
                                'entity_name': '迎客松'}, ensure_ascii=False)
    entity_decision = json.dumps({'action': 'entity', 'args': {'scenic': '黄山', 'name': '迎客松'},
                                  'reason': '用户询问实体提及统计。'}, ensure_ascii=False)
    def entity_answer(payload):
        content = payload['messages'][1]['content']
        raw = content.split('实体/其他工具结果（JSON）：', 1)[1].split('\n风险提示：', 1)[0]
        match = json.loads(raw)['matches'][0]
        return '图谱记录显示，%s 被提及 %s 次。' % (match['label'], match['mention_count'])
    entity_result, entity_calls = run_mocked_query(entity_query,
                                                   [entity_intent, entity_decision, entity_answer])
    entity_match = entity_result['plan'].get('answer_context', {}).get('matches', [{}])[0]
    entity_ok = [c['action'] for c in entity_result['tool_calls']] == ['entity'] \
        and entity_result['plan'].get('evidence_ids') and entity_match.get('mention_count') is not None \
        and str(entity_match['mention_count']) in entity_result['plan']['summary'] \
        and '迎客松' in entity_result['plan']['summary'] and len(entity_calls) == 3
    check('llm_entity_tool_result_answers_entity_question', bool(entity_ok),
          '单实体问题调用 entity；最终答复复用图谱 mention_count 和证据')

    advice_query = '黄山有哪些老人出行建议？'
    advice_intent = json.dumps({'scenic': '黄山', 'visitor_type': '老人', 'duration': 1,
                                'preferences': [], 'constraints': [], 'need_clarification': False,
                                'task_type': 'advice', 'entity_name': None}, ensure_ascii=False)
    advice_decision = json.dumps({'action': 'advice',
                                  'args': {'scenic': '黄山', 'traveler_type': '老人', 'limit': 6},
                                  'reason': '这是建议问句，不需要取路线。'}, ensure_ascii=False)
    def advice_answer(payload):
        content = payload['messages'][1]['content']
        raw = content.split('条件建议（JSON）：', 1)[1].split('\n实体/其他工具结果', 1)[0]
        row = json.loads(raw)[0]
        return '图谱建议（%s）：%s' % (row['condition'], row['advice'])
    advice_result, advice_calls = run_mocked_query(advice_query,
                                                   [advice_intent, advice_decision, advice_answer])
    advice_first = advice_result['plan'].get('advices', [{}])[0]
    advice_ok = [c['action'] for c in advice_result['tool_calls']] == ['advice'] \
        and not advice_result['plan'].get('days') and advice_result['plan'].get('evidence_ids') \
        and advice_first.get('advice') in advice_result['plan']['summary'] and len(advice_calls) == 3
    check('llm_advice_question_skips_route_and_uses_result', bool(advice_ok),
          '单建议问题只调用 advice，最终答复使用返回建议及证据')

    general_query = '图谱收录了哪些景区？'
    general_intent = json.dumps({'scenic': None, 'unknown_scenic': '', 'visitor_type': '普通',
                                 'duration': 1, 'preferences': [], 'constraints': [],
                                 'need_clarification': False, 'task_type': 'general',
                                 'entity_name': None}, ensure_ascii=False)
    general_decision = json.dumps({'action': 'scenics', 'args': {},
                                   'reason': '用户问收录范围，查询景区清单。'}, ensure_ascii=False)
    def general_answer(payload):
        content = payload['messages'][1]['content']
        raw = content.split('实体/其他工具结果（JSON）：', 1)[1].split('\n风险提示：', 1)[0]
        names = json.loads(raw)['available']
        return '图谱目前收录：' + '、'.join(names) + '。'
    general_result, general_calls = run_mocked_query(general_query,
                                                     [general_intent, general_decision, general_answer])
    scenic_names = general_result['plan'].get('answer_context', {}).get('available', [])
    general_ok = [c['action'] for c in general_result['tool_calls']] == ['scenics'] \
        and scenic_names and all(n in general_result['plan']['summary'] for n in scenic_names) \
        and len(general_calls) == 3
    check('llm_general_question_uses_scenics_result', bool(general_ok),
          '收录范围问题调用 scenics，答复列出工具实际返回的景区')

    vague_intent = json.dumps({'scenic': None, 'unknown_scenic': '', 'visitor_type': '普通',
                               'duration': 1, 'preferences': [], 'constraints': [],
                               'need_clarification': True, 'task_type': 'route',
                               'entity_name': None}, ensure_ascii=False)
    stop_decision = json.dumps({'action': 'stop', 'args': {},
                                'reason': '缺少景区、同行人群和天数，先追问。'}, ensure_ascii=False)
    vague_result, vague_calls = run_mocked_query('帮我做个旅游规划', [vague_intent, stop_decision])
    vague_decision_ok = not vague_result['tool_calls'] and vague_result['llm']['decision_accepted'] == 1 \
        and vague_result['traces'][-1]['type'] == 'final' \
        and '请补充' in vague_result['plan']['summary'] and len(vague_calls) == 2
    check('llm_decision_stops_and_clarifies', bool(vague_decision_ok),
          '模型决定不查图谱并追问；无工具调用、无猜测行程')

    bad_action_intent = json.dumps({'scenic': '黄山', 'unknown_scenic': '', 'visitor_type': '老人',
                                    'duration': 1, 'preferences': [], 'constraints': [],
                                    'need_clarification': False, 'task_type': 'route'}, ensure_ascii=False)
    wrong_action = json.dumps({'action': 'route', 'args': {'scenic': '张家界'},
                               'reason': '错误地改选景区。'}, ensure_ascii=False)
    valid_advice = json.dumps({'action': 'advice',
                               'args': {'scenic': '黄山', 'traveler_type': '老人', 'limit': 6},
                               'reason': '读取老人建议。'}, ensure_ascii=False)
    valid_plan = json.dumps({'day_assignments': [{'order': i, 'day': 1} for i in range(1, 15)],
                             'pace': '轻松', 'rationale': '保持图谱顺序并照顾老人同行。'}, ensure_ascii=False)
    invalid_decision_result, invalid_decision_calls = run_mocked_query(
        '带老人去黄山玩一天', [bad_action_intent, wrong_action, valid_advice,
                               valid_plan, '黄山行程使用图谱路线，未核验通行。'])
    invalid_decision_ok = [c['action'] for c in invalid_decision_result['tool_calls']] == ['route', 'advice'] \
        and invalid_decision_result['llm']['fallback_count'] == 1 \
        and invalid_decision_result['llm']['fallback_events'][0]['stage'] == 'decision' \
        and invalid_decision_result['plan']['scenic'] == '黄山' and len(invalid_decision_calls) == 5
    check('llm_invalid_tool_decision_uses_safe_fallback', bool(invalid_decision_ok),
          '模型动作与明确景区冲突时拒绝执行，并以规则路线恢复')

    import urllib.error
    import http.client
    def failed_post(url, payload, headers, timeout):
        # A peer may close the socket before sending an HTTP status. This is an
        # OSError (RemoteDisconnected), not always wrapped as urllib.URLError.
        raise http.client.RemoteDisconnected('simulated peer closed connection')
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'local-test-key',
                                 'OPENAI_BASE_URL': 'https://mock.invalid/v1',
                                 'OPENAI_MODEL': 'mock-model'}), patch.object(llm_mod, '_post_json', failed_post):
        failed_result = ReActAgent(tool=tool, llm=LLMClient()).run('带老人去黄山玩一天')
    failed_ok = failed_result['plan']['found'] and failed_result['plan']['summary'] \
        and failed_result['llm']['request_attempts'] == 5 \
        and failed_result['llm']['successful_responses'] == 0 \
        and failed_result['llm']['fallback_count'] == 5 \
        and sum(e.get('stage') == 'decision' for e in failed_result['llm']['fallback_events']) == 2 \
        and 'local-test-key' not in json.dumps(failed_result, ensure_ascii=False)
    check('llm_http_failure_falls_back', bool(failed_ok),
          '模拟连接失败后仍生成规则方案；请求=%d，回退=%d' %
          (failed_result['llm']['request_attempts'], failed_result['llm']['fallback_count']))

    malformed_calls = []
    def malformed_then_reply(url, payload, headers, timeout):
        malformed_calls.append(url)
        if len(malformed_calls) == 1:
            content = 'not-json'
        elif len(malformed_calls) == 2:
            content = json.dumps({'action': 'route', 'args': {'scenic': '黄山'},
                                  'reason': '读取明确景区路线。'}, ensure_ascii=False)
        elif len(malformed_calls) == 3:
            content = json.dumps({'action': 'advice', 'args': {'scenic': '黄山',
                                  'traveler_type': '老人', 'limit': 6},
                                  'reason': '读取老人建议。'}, ensure_ascii=False)
        elif len(malformed_calls) == 4:
            content = json.dumps({
                'day_assignments': [{'order': i, 'day': 1} for i in range(1, 15)],
                'pace': '轻松', 'rationale': '按用户偏好沿用图谱步骤安排。'
            }, ensure_ascii=False)
        else:
            content = '模拟模型行程回答。'
        return {'choices': [{'message': {'content': content}}]}
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'local-test-key',
                                 'OPENAI_BASE_URL': 'https://mock.invalid/v1',
                                 'OPENAI_MODEL': 'mock-model'}), patch.object(llm_mod, '_post_json', malformed_then_reply):
        malformed_result = ReActAgent(tool=tool, llm=LLMClient()).run('带老人去黄山玩一天')
    used_rules = any(t['type'] == 'thought' and t['content'].startswith('[rules]')
                     for t in malformed_result['traces'])
    malformed_ok = malformed_result['plan']['found'] and used_rules \
        and malformed_result['llm']['failures'] == 1 \
        and malformed_result['llm']['fallback_count'] == 1 \
        and malformed_result['llm']['successful_responses'] == 5 \
        and malformed_result['plan']['llm_planning']['status'] == 'accepted'
    check('llm_invalid_intent_json_falls_back', bool(malformed_ok),
          '意图非法 JSON 回退规则解析，后续回答仍可生成')

    composition_calls = []
    def fail_final_compose(url, payload, headers, timeout):
        composition_calls.append(url)
        if len(composition_calls) == 1:
            content = json.dumps({'scenic': '黄山', 'unknown_scenic': '', 'visitor_type': '老人',
                                  'duration': 1, 'preferences': [], 'constraints': [],
                                  'need_clarification': False})
            return {'choices': [{'message': {'content': content}}]}
        if len(composition_calls) == 2:
            return {'choices': [{'message': {'content': json.dumps({'action': 'route',
                    'args': {'scenic': '黄山'}, 'reason': '按景区查路线。'}, ensure_ascii=False)}}]}
        if len(composition_calls) == 3:
            return {'choices': [{'message': {'content': json.dumps({'action': 'advice',
                    'args': {'scenic': '黄山', 'traveler_type': '老人', 'limit': 6},
                    'reason': '查询老人适配建议。'}, ensure_ascii=False)}}]}
        if len(composition_calls) == 4:
            content = json.dumps({
                'day_assignments': [{'order': i, 'day': 1} for i in range(1, 15)],
                'pace': '轻松', 'rationale': '按用户偏好沿用图谱步骤安排。'
            }, ensure_ascii=False)
            return {'choices': [{'message': {'content': content}}]}
        raise urllib.error.URLError('simulated final-response failure')
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'local-test-key',
                                 'OPENAI_BASE_URL': 'https://mock.invalid/v1',
                                 'OPENAI_MODEL': 'mock-model'}), patch.object(llm_mod, '_post_json', fail_final_compose):
        final_failed = ReActAgent(tool=tool, llm=LLMClient()).run('带老人去黄山玩一天')
    compose_note = any(t['type'] == 'note' and '最终回答生成失败' in t['content']
                       for t in final_failed['traces'])
    compose_ok = final_failed['plan']['found'] and compose_note \
        and final_failed['llm']['successful_responses'] == 4 \
        and final_failed['llm']['fallback_count'] == 1 \
        and '黄山' in final_failed['plan']['summary']
    check('llm_final_answer_failure_visible', bool(compose_ok),
          '意图成功、回答接口失败时显示回退并保留可用方案')

    invalid_plan_calls = []
    def invalid_plan_then_answer(url, payload, headers, timeout):
        invalid_plan_calls.append(url)
        if len(invalid_plan_calls) == 1:
            content = json.dumps({'scenic': '黄山', 'unknown_scenic': '', 'visitor_type': '老人',
                                  'duration': 1, 'preferences': [], 'constraints': [],
                                  'need_clarification': False})
        elif len(invalid_plan_calls) == 2:
            content = json.dumps({'action': 'route', 'args': {'scenic': '黄山'},
                                  'reason': '查询路线。'}, ensure_ascii=False)
        elif len(invalid_plan_calls) == 3:
            content = json.dumps({'action': 'advice', 'args': {'scenic': '黄山',
                                  'traveler_type': '老人', 'limit': 6},
                                  'reason': '查询人群建议。'}, ensure_ascii=False)
        elif len(invalid_plan_calls) == 4:
            content = json.dumps({
                'day_assignments': [{'order': i, 'day': 1 if i != 14 else 2} for i in range(1, 15)],
                'pace': '轻松', 'rationale': '有一步被错误分到第二天。'
            }, ensure_ascii=False)
        else:
            content = '黄山一日方案。'
        return {'choices': [{'message': {'content': content}}]}
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'local-test-key',
                                 'OPENAI_BASE_URL': 'https://mock.invalid/v1',
                                 'OPENAI_MODEL': 'mock-model'}), patch.object(llm_mod, '_post_json', invalid_plan_then_answer):
        invalid_plan = ReActAgent(tool=tool, llm=LLMClient()).run('带老人去黄山玩一天')
    invalid_plan_ok = invalid_plan['plan']['llm_planning']['status'] == 'rejected' \
        and invalid_plan['llm']['fallback_count'] == 1 \
        and invalid_plan['plan']['days'][0]['day'] == 1 \
        and len([s for d in invalid_plan['plan']['days'] for sec in d['sections'] for s in sec['steps']]) == 14 \
        and '未通过图谱步骤与用户约束校验' in ' '.join(invalid_plan['plan']['notes'])
    check('llm_plan_proposal_graph_guard', bool(invalid_plan_ok),
          '非法分日被拒绝，保留 14 个图谱步骤并用规则计划回退')

    # 14 CLI 可用
    import subprocess
    p = subprocess.run([sys.executable, str(HERE / 'cli.py'), '--offline', '--trace',
                        '--query', '情侣一日黄山'], capture_output=True, text=True)
    check('cli_runs', p.returncode == 0 and '方案' in p.stdout, p.returncode and p.stderr[-300:])

    # 15 Test catalog is the traceable index for every scenario/acceptance/live case.
    catalog = json.loads((DATA / 'test_catalog.json').read_text(encoding='utf-8'))
    catalog_cases = catalog.get('cases', [])
    ids = [c.get('id') for c in catalog_cases]
    scenario_ids = {c['id'] for c in json.loads((ROOT / 'data/lab7/scenarios.json').read_text(
        encoding='utf-8'))['scenarios']}
    acceptance_ids = {c['id'] for c in checks} | {'test_catalog_consistent'}
    scenario_refs = {c['source'].split('#', 1)[1] for c in catalog_cases
                     if c.get('group') == 'scenario' and '#' in c.get('source', '')}
    acceptance_refs = {c['source'].split('#', 1)[1] for c in catalog_cases
                       if c.get('group') == 'acceptance' and '#' in c.get('source', '')}
    live_refs = {c['source'].split('#', 1)[1] for c in catalog_cases
                 if c.get('group') == 'live' and '#' in c.get('source', '')}
    counts_ok = all(group.get('count') == sum(c.get('group') == group.get('id') for c in catalog_cases)
                    for group in catalog.get('groups', []))
    catalog_ok = bool(catalog_cases) and None not in ids and len(ids) == len(set(ids)) \
        and all(c.get('expected') for c in catalog_cases) \
        and scenario_refs == scenario_ids \
        and live_refs == scenario_ids \
        and acceptance_refs == acceptance_ids \
        and counts_ok \
        and all(g.get('runner') == 'src/lab7/online_tests.py' for g in catalog.get('groups', [])
                if g.get('id') == 'live')
    check('test_catalog_consistent', catalog_ok,
          '登记 %d 项；离线场景 %d/8、自动验收 %d 项、在线场景 %d/8' %
          (len(catalog_cases), len(scenario_refs), len(acceptance_refs), len(live_refs)))

    passed = sum(c['passed'] for c in checks)
    result = {
        'checks': checks,
        'summary': {'passed': passed, 'total': len(checks), 'all_passed': passed == len(checks)},
        'evidence_sources': {f: {'count': n, 'desc': UPSTREAM.get(f, '其他')} for f, n in sorted(files.items())},
        'graph_sha256': sha,
    }
    (OUT / 'acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    for c in checks:
        print('%s %s :: %s' % ('PASS' if c['passed'] else 'FAIL', c['id'], c['detail']))
    print('\n%d/%d 项通过' % (passed, len(checks)))
    return 0 if passed == len(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
