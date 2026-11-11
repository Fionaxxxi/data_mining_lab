"""多场景测试：跑 8 类约束场景，保存可核验的工具轨迹与方案。

输出：
  outputs/lab7/test_cases.json   每例的意图、方案摘要、调用次数与期望核对
  outputs/lab7/traces.jsonl      每例完整 ReAct 轨迹
  outputs/lab7/queries.json      实际发出的工具参数与返回摘要
  outputs/lab7/test_run.log      运行日志
任一期望不满足时退出码非 0。
"""
from pathlib import Path
import json
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agent import ReActAgent  # noqa: E402
from graph_tool import KGQueryTool  # noqa: E402
from llm import LLMClient  # noqa: E402

ROOT = HERE.parents[1]
DATA = ROOT / 'data/lab7'
OUT = ROOT / 'outputs/lab7'


def plan_steps(plan):
    return [st for day in plan.get('days', []) for sec in day['sections'] for st in sec['steps']]


def check_expect(name, got, expect):
    """返回 (是否通过, 说明)。"""
    problems = []
    if 'scenic' in expect and got['scenic'] != expect['scenic']:
        problems.append('scenic=%r 期望 %r' % (got['scenic'], expect['scenic']))
    if expect.get('scenic_null') and got['scenic'] is not None:
        problems.append('scenic 应为空，实际 %r' % got['scenic'])
    if expect.get('scenic_not_null') and got['scenic'] is None:
        problems.append('scenic 不应为空')
    if 'visitor_type' in expect and got['visitor_type'] != expect['visitor_type']:
        problems.append('visitor_type=%r' % got['visitor_type'])
    if 'duration' in expect and got['duration'] != expect['duration']:
        problems.append('duration=%r' % got['duration'])
    if 'found' in expect and got['found'] != expect['found']:
        problems.append('found=%r 期望 %r' % (got['found'], expect['found']))
    if expect.get('need_clarification') and not got['need_clarification']:
        problems.append('应追问')
    if 'min_tool_calls' in expect and got['tool_call_count'] < expect['min_tool_calls']:
        problems.append('工具调用 %d < %d' % (got['tool_call_count'], expect['min_tool_calls']))
    if 'max_tool_calls' in expect and got['tool_call_count'] > expect['max_tool_calls']:
        problems.append('工具调用 %d > %d' % (got['tool_call_count'], expect['max_tool_calls']))
    if 'days' in expect and len(got['days']) != expect['days']:
        problems.append('天数段落 %d' % len(got['days']))
    if 'min_steps' in expect and got['step_count'] < expect['min_steps']:
        problems.append('步骤 %d' % got['step_count'])
    if expect.get('no_plan') and got['step_count']:
        problems.append('不应生成行程，实际 %d 步' % got['step_count'])
    if expect.get('selection_used') and not got['selection_used']:
        problems.append('未记录择优依据')
    for w in expect.get('warnings_any', []):
        if w not in got['warnings']:
            problems.append('提示缺少关键词 %r' % w)
    if 'advice_contains' in expect:
        if expect['advice_contains'] not in got['advice_text']:
            problems.append('建议未包含 %r' % expect['advice_contains'])
    if 'message_contains' in expect and expect['message_contains'] not in got['message']:
        problems.append('说明未包含 %r' % expect['message_contains'])
    return (not problems), '；'.join(problems)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = json.loads((DATA / 'scenarios.json').read_text(encoding='utf-8'))['scenarios']
    tool = KGQueryTool()
    llm = LLMClient()
    agent = ReActAgent(tool=tool, llm=llm)
    log = ['实验七 多场景测试（LLM 后端：%s，图谱 sha256=%s）' % (llm.provider, tool.sha256[:16]),
           '图谱来源：%s' % tool.graph_path]
    rows, failures = [], 0
    traces_lines = []
    queries = []

    for sc in scenarios:
        t0 = time.time()
        res = agent.run(sc['query'])
        plan = res['plan']
        steps = plan_steps(plan)
        got = {
            'scenic': plan.get('scenic'), 'visitor_type': plan.get('visitor_type'),
            'duration': plan.get('duration'), 'found': plan.get('found'),
            'need_clarification': bool(plan.get('need_clarification')),
            'tool_call_count': res['tool_call_count'], 'step_count': len(steps),
            'days': plan.get('days', []), 'warnings': ' '.join(plan.get('warnings', [])) + ' ' + ' '.join(plan.get('notes', [])),
            'advice_text': ' '.join(a['condition'] + a['advice'] for a in plan.get('advices', [])),
            'selection_used': bool(plan.get('selection')),
            'message': (plan.get('message') or '') + (plan.get('clarify_message') or ''),
        }
        ok, why = check_expect(sc['id'], got, sc['expect'])
        if not ok:
            failures += 1
        rows.append({
            'id': sc['id'], 'tag': sc['tag'], 'query': sc['query'],
            'expect': sc['expect'], 'expect_ok': ok, 'expect_problem': why,
            'provider': res['provider'],
            'intent': {k: res['intent'][k] for k in
                       ('scenic', 'unknown_scenic', 'visitor_type', 'duration', 'preferences', 'constraints',
                        'need_clarification', 'flags')},
            'found': plan.get('found'), 'need_clarification': got['need_clarification'],
            'scenic': plan.get('scenic'), 'step_count': len(steps),
            'days': [{'day': d['day'], 'sections': [
                {'period': s['period'], 'steps': ['%02d %s (%s)' % (x['order'], x['spot'], x['period_status'])
                                                   for x in s['steps']]}
                for s in d['sections']]} for d in plan.get('days', [])],
            'period_source': plan.get('period_source'), 'period_repairs': plan.get('period_repairs', []),
            'selection': plan.get('selection'), 'advices': [
                {'mapping_id': a['mapping_id'], 'condition': a['condition'], 'advice': a['advice'],
                 'traveler_type': a['traveler_type'], 'negative': a['negative'],
                 'historical_only': a['historical_only'], 'evidence_refs': a['evidence_refs']}
                for a in plan.get('advices', [])],
            'warnings': plan.get('warnings', []), 'notes': plan.get('notes', []),
            'summary': plan.get('summary'), 'message': plan.get('message'),
            'evidence_count': len(plan.get('evidence_ids', [])),
            'evidence_ids': plan.get('evidence_ids', []),
            'tool_call_count': res['tool_call_count'], 'error_count': res['error_count'],
            'tool_calls': res['tool_calls'], 'trace_step_count': len(res['traces']),
            'elapsed_ms': int((time.time() - t0) * 1000),
        })
        traces_lines.append(json.dumps({'id': sc['id'], 'query': sc['query'], 'traces': res['traces']},
                                       ensure_ascii=False))
        queries.append({'id': sc['id'], 'calls': [
            {'args': c} for c in res['tool_calls']]})
        log.append('[%s] %s 工具=%d 步=%d 命中=%s 期望=%s%s' % (
            sc['id'], sc['tag'], res['tool_call_count'], len(steps), plan.get('found'),
            '通过' if ok else '失败', '' if ok else '（' + why + '）'))
        log.append('    方案：' + (plan.get('summary') or '').replace('\n', ' ')[:180])

    (OUT / 'test_cases.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (OUT / 'traces.jsonl').write_text('\n'.join(traces_lines) + '\n', encoding='utf8')
    (OUT / 'queries.json').write_text(json.dumps(queries, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (OUT / 'meta.json').write_text(json.dumps({
        'lab': 7, 'provider': llm.provider, 'graph_path': str(tool.graph_path.relative_to(ROOT)),
        'graph_sha256': tool.sha256, 'scenario_count': len(rows),
        'tool_name': 'knowledge_graph_query',
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (OUT / 'test_run.log').write_text('\n'.join(log) + '\n', encoding='utf8')
    print('\n'.join(log))
    print('\n共 %d 例，期望核对失败 %d 例。' % (len(rows), failures))
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
