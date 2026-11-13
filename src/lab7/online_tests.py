"""Serial real-LLM scenario suite. Never retries and never writes credentials."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / 'data/lab7'
OUT = ROOT / 'outputs/lab7'
sys.path.insert(0, str(HERE))

from agent import ReActAgent  # noqa: E402
from graph_tool import KGQueryTool  # noqa: E402
from llm import LLMClient  # noqa: E402
from tests import check_expect, plan_steps  # noqa: E402


def _intent_source(result):
    for item in result.get('traces', []):
        if item.get('type') == 'thought' and item.get('intent_source'):
            return item['intent_source']
    return None


def _case_result(scenario, tool):
    llm = LLMClient()
    if not llm.online:
        return {
            'id': scenario['id'], 'tag': scenario['tag'], 'query': scenario['query'],
            'passed': False, 'problems': ['未配置在线 LLM 凭证；未发送请求'],
            'provider': llm.provider, 'llm': llm.diagnostics(),
        }

    result = ReActAgent(tool=tool, llm=llm).run(scenario['query'])
    plan = result['plan']
    steps = plan_steps(plan)
    advice_text = '；'.join(a.get('condition', '') + ' ' + a.get('advice', '')
                            for a in plan.get('advices', []))
    got = {
        'scenic': plan.get('scenic'), 'visitor_type': result['intent'].get('visitor_type'),
        'duration': plan.get('duration'), 'found': plan.get('found'),
        'need_clarification': plan.get('need_clarification', False),
        'tool_call_count': result.get('tool_call_count', 0), 'days': plan.get('days', []),
        'step_count': len(steps), 'selection_used': bool(plan.get('selection')),
        'warnings': plan.get('warnings', []), 'advice_text': advice_text,
        'message': plan.get('message', ''),
    }
    ok, why = check_expect(scenario['id'], got, scenario['expect'])
    problems = [] if ok else [why]
    diag = result.get('llm', {})
    source = _intent_source(result)
    if source != 'llm':
        problems.append('意图解析未由真实 LLM 成功提供')
    if diag.get('request_attempts', 0) != diag.get('successful_responses', 0):
        problems.append('存在未成功的 LLM 请求')
    if diag.get('failures', 0) or diag.get('fallback_count', 0):
        problems.append('发生模型失败或规则回退')
    if diag.get('decision_attempts', 0) != diag.get('decision_accepted', 0):
        problems.append('一个或多个 LLM 工具决策未通过校验')
    decisions = [t for t in result.get('traces', [])
                 if t.get('decision_source') == 'llm' and t.get('decision')]
    if not decisions:
        problems.append('执行轨迹没有记录真实 LLM 的工具/停止决策')
    if plan.get('found') and plan.get('days'):
        proposal = plan.get('llm_planning') or {}
        if proposal.get('status') != 'accepted' or diag.get('planning_accepted') != 1:
            problems.append('模型规划提案未通过结构与图谱事实校验')
        route = tool.run({'action': 'route', 'scenic': plan.get('scenic')})
        allowed = {(s.get('step_id'), s.get('order')) for s in route.get('steps', [])}
        outside = [(s.get('step_id'), s.get('order')) for s in steps
                   if (s.get('step_id'), s.get('order')) not in allowed]
        if outside:
            problems.append('行程包含图谱路线外步骤: %r' % outside[:3])
        summary = plan.get('summary', '')
        if steps and not any(s.get('spot') and s['spot'] in summary for s in steps):
            problems.append('最终回答没有复用任何图谱路线地点')
        advice_rows = plan.get('advices', [])
        if advice_rows and not any((a.get('condition') and a['condition'] in summary)
                                   or (a.get('advice') and a['advice'] in summary)
                                   for a in advice_rows):
            problems.append('最终回答没有复用已查询到的建议内容')
    expected_calls = (1 + diag.get('decision_attempts', 0) + diag.get('planning_attempts', 0)
                      + (1 if plan.get('found') and not plan.get('need_clarification') else 0))
    if diag.get('request_attempts') != expected_calls:
        problems.append('请求次数 %s，期望 %d（意图/规划/回答按分支执行）'
                        % (diag.get('request_attempts'), expected_calls))

    api_key = llm.api_key
    row = {
        'id': scenario['id'], 'tag': scenario['tag'], 'query': scenario['query'],
        'passed': not problems, 'problems': problems,
        'provider': result.get('provider'), 'intent_source': source,
        'intent': result.get('intent'), 'plan': plan,
        'tool_calls': result.get('tool_calls'), 'traces': result.get('traces'),
        'llm': diag, 'graph_sha256': result.get('graph_sha256'),
    }
    serialized = json.dumps(row, ensure_ascii=False)
    if api_key:
        serialized = serialized.replace(api_key, '[REDACTED]')
    return json.loads(serialized)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = json.loads((DATA / 'scenarios.json').read_text(encoding='utf-8'))['scenarios']
    tool = KGQueryTool()
    probe = LLMClient()
    if not probe.online:
        print('未配置在线 LLM；没有发出请求。请检查仓库根目录 .env。', file=sys.stderr)
        return 2
    started = datetime.now(timezone.utc).isoformat()
    print('实验七完整在线场景测试：%d 例，串行执行，不自动重试。' % len(scenarios))
    print('Provider=%s；图谱 sha256=%s' % (probe.provider, tool.sha256[:16]))
    rows = []
    for scenario in scenarios:
        try:
            row = _case_result(scenario, tool)
        except Exception as ex:
            row = {
                'id': scenario['id'], 'tag': scenario['tag'], 'query': scenario['query'],
                'passed': False, 'problems': ['运行异常：%s: %s' % (type(ex).__name__, ex)],
            }
        rows.append(row)
        diag = row.get('llm', {})
        print('%s %s :: HTTP %s/%s，决策 %s/%s，回退 %s%s' % (
            'PASS' if row['passed'] else 'FAIL', row['id'],
            diag.get('successful_responses', 0), diag.get('request_attempts', 0),
            diag.get('decision_accepted', 0), diag.get('decision_attempts', 0),
            diag.get('fallback_count', 0),
            ('；' + '；'.join(row.get('problems', []))) if row.get('problems') else ''))

    passed = sum(bool(row.get('passed')) for row in rows)
    payload = {
        'suite': 'lab7_online_scenarios', 'started_at': started,
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'provider': probe.provider, 'graph_sha256': tool.sha256,
        'scenario_count': len(rows), 'summary': {
            'passed': passed, 'failed': len(rows) - passed, 'all_passed': passed == len(rows),
            'request_attempts': sum(r.get('llm', {}).get('request_attempts', 0) for r in rows),
            'successful_responses': sum(r.get('llm', {}).get('successful_responses', 0) for r in rows),
            'decision_attempts': sum(r.get('llm', {}).get('decision_attempts', 0) for r in rows),
            'decision_accepted': sum(r.get('llm', {}).get('decision_accepted', 0) for r in rows),
            'fallbacks': sum(r.get('llm', {}).get('fallback_count', 0) for r in rows),
        },
        'cases': rows,
    }
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    runs_dir = OUT / 'online_runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    data_path = OUT / 'online_test_results.json'
    log_path = OUT / 'online_test_run.log'
    serialized_payload = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    data_path.write_text(serialized_payload, encoding='utf-8')
    log_lines = [
        'Lab 7 online scenario run', 'started_at=' + started,
        'provider=' + probe.provider, 'graph_sha256=' + tool.sha256,
    ]
    for row in rows:
        diag = row.get('llm', {})
        log_lines.append('%s %s requests=%s successes=%s decisions=%s/%s fallbacks=%s problems=%s' % (
            'PASS' if row.get('passed') else 'FAIL', row['id'],
            diag.get('request_attempts', 0), diag.get('successful_responses', 0),
            diag.get('decision_accepted', 0), diag.get('decision_attempts', 0),
            diag.get('fallback_count', 0), ' | '.join(row.get('problems', []))))
    summary = payload['summary']
    log_lines.append('summary=%d/%d passed requests=%d successes=%d decisions=%d/%d fallbacks=%d' % (
        passed, len(rows), summary['request_attempts'], summary['successful_responses'],
        summary['decision_accepted'], summary['decision_attempts'], summary['fallbacks']))
    serialized_log = '\n'.join(log_lines) + '\n'
    log_path.write_text(serialized_log, encoding='utf-8')
    (runs_dir / ('%s.json' % stamp)).write_text(serialized_payload, encoding='utf-8')
    (runs_dir / ('%s.log' % stamp)).write_text(serialized_log, encoding='utf-8')
    print('在线测试结果：%d/%d 通过；明细：%s' % (passed, len(rows), data_path))
    return 0 if passed == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
