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
    agent = ReActAgent(tool=KGQueryTool(), llm=LLMClient())
    r1 = agent.run('带老人去黄山玩一天，希望行程轻松平缓')
    r2 = ReActAgent(tool=KGQueryTool(), llm=LLMClient()).run('带老人去黄山玩一天，希望行程轻松平缓')
    same = json.dumps(r1['plan']['days'], ensure_ascii=False) == json.dumps(r2['plan']['days'], ensure_ascii=False) \
        and r1['plan']['summary'] == r2['plan']['summary']
    check('deterministic_offline', same, '两次运行的 days 与 summary %s' % ('一致' if same else '不一致'))
    check('provider_offline_when_no_key', r1['provider'] == 'offline-rules' or r1['provider'].startswith('openai-compatible'),
          'provider=%s' % r1['provider'])

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
        else:
            content = '黄山一日行程；以上景点均来自图谱，实际通行未核验。'
        return {'choices': [{'message': {'content': content}}]}
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'local-test-key',
                                 'OPENAI_BASE_URL': 'https://mock.invalid/v1',
                                 'OPENAI_MODEL': 'mock-model'}), patch.object(llm_mod, '_post_json', fake_post):
        simulated = ReActAgent(tool=tool, llm=LLMClient()).run('带老人去黄山玩一天')
    online_ok = len(calls) == 2 and simulated['intent']['scenic'] == '黄山' \
        and simulated['intent']['visitor_type'] == '老人' and simulated['intent']['duration'] == 1 \
        and simulated['plan']['scenic'] == '黄山' and simulated['plan']['found'] \
        and calls[0]['url'] == 'https://mock.invalid/v1/chat/completions' \
        and calls[0]['headers'].get('Authorization') == 'Bearer local-test-key'
    check('llm_mock_input_output_chain', online_ok,
          '本地模拟调用 %d 次；明确景区保留为 %s；未测试真实外部 API' %
          (len(calls), simulated['plan']['scenic']))

    # 14 CLI 可用
    import subprocess
    p = subprocess.run([sys.executable, str(HERE / 'cli.py'), '--query', '情侣一日黄山'], capture_output=True, text=True)
    check('cli_runs', p.returncode == 0 and '方案' in p.stdout, p.returncode and p.stderr[-300:])

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
