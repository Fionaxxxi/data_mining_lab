"""命令行交互入口：单次提问或交互循环。

示例：
  python src/lab7/cli.py --query "带老人去黄山玩一天"
  python src/lab7/cli.py --interactive --trace
  python src/lab7/cli.py --query "亲子九寨沟一日游" --json
"""
import argparse
import json
import sys

from agent import ReActAgent


def print_trace(result):
    print('-' * 72)
    llm = result.get('llm', {})
    print('LLM 配置：', result['provider'],
          '｜HTTP 请求：%d 次，成功响应：%d 次，回退：%d 次' % (
              llm.get('request_attempts', 0), llm.get('successful_responses', 0),
              llm.get('fallback_count', 0)),
          '｜图谱工具调用：', result['tool_call_count'], '次')
    if llm.get('last_error'):
        print('LLM 最近错误：', llm['last_error'])
    print('-' * 72)
    for t in result['traces']:
        typ = t['type'].upper()
        if typ == 'ACTION':
            print('[ACTION] %s %s' % (t.get('tool'), json.dumps(t.get('args'), ensure_ascii=False)))
        elif typ == 'OBSERVATION':
            print('[OBSERVATION] %s' % t['content'])
        elif typ == 'THOUGHT':
            print('[THOUGHT] %s' % t['content'])
        elif typ == 'NOTE':
            print('[NOTE] %s' % t['content'])
        else:
            print('[FINAL] %s' % t['content'])
        print('-' * 72)


def print_plan(result):
    plan = result['plan']
    print(plan.get('summary', ''))
    print()
    if plan.get('found') and plan.get('days'):
        print('结构化行程（JSON 摘要）：')
        brief = {
            'scenic': plan['scenic'], 'visitor_type': plan['visitor_type'],
            'duration': plan['duration'], 'period_source': plan.get('period_source'),
            'days': [{'day': d['day'],
                      'sections': [{'period': s['period'],
                                    'steps': ['%02d %s (%s)' % (x['order'], x['spot'], x['period_status'])
                                              for x in s['steps']]} for s in d['sections']]}
                     for d in plan['days']],
            'advice_count': len(set(a['mapping_id'] for a in plan['advices'])),
            'evidence_count': len(plan['evidence_ids']),
        }
        print(json.dumps(brief, ensure_ascii=False, indent=2))
    if plan.get('notes'):
        print('说明：')
        for n in plan['notes']:
            print(' -', n)
    if plan.get('warnings'):
        print('注意：')
        for w in plan['warnings']:
            print(' -', w)


def main():
    ap = argparse.ArgumentParser(description='实验七 旅游规划 Agent（复用实验六图谱）')
    ap.add_argument('--query', help='单次用户请求')
    ap.add_argument('--interactive', action='store_true', help='进入交互循环')
    ap.add_argument('--trace', action='store_true', help='打印 ReAct 轨迹')
    ap.add_argument('--json', action='store_true', help='输出完整 JSON')
    ap.add_argument('--offline', action='store_true', help='强制使用离线规则，不读取本机 .env')
    a = ap.parse_args()
    from llm import LLMClient
    agent = ReActAgent(llm=LLMClient(force_offline=a.offline))

    def handle(q):
        r = agent.run(q)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return
        if a.trace:
            print_trace(r)
        print('=' * 72)
        print('用户请求：', q)
        print('=' * 72)
        print_plan(r)
        print()

    if a.interactive or not a.query:
        print('输入旅游请求，空行或 exit 退出。')
        while True:
            try:
                q = input('> ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q or q.lower() in ('exit', 'quit'):
                break
            handle(q)
    else:
        handle(a.query)
    return 0


if __name__ == '__main__':
    sys.exit(main())
