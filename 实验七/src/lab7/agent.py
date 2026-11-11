"""ReAct Agent：解析 → 决策 → 调工具 → 读结果 → 生成，全程留轨迹。

工具调用是真实发生的：每次 Action 都会执行 KGQueryTool.run，Observation 是它的返回摘要；
最终方案由规划器只用这些 Observation 组装。离线模式不调用模型，但闭环与工具编排不变。
"""
from pathlib import Path
import json

import intent as intent_mod
import planner
from graph_tool import KGQueryTool, TOOL_SPEC
from llm import LLMClient

ROOT = Path(__file__).resolve().parents[2]
MAX_STEPS = 6


def _obs_digest(action, res):
    if not res.get('ok'):
        return {'ok': False, 'error': res.get('error')}
    if action == 'scenics':
        return {'ok': True, 'scenics': [{'scenic': s['scenic'], 'steps': s['step_count'],
                                         'conditions': s['condition_count']}
                                        for s in res['scenics']]}
    if action == 'route':
        if not res.get('found'):
            return {'ok': True, 'found': False, 'available': res.get('available')}
        return {'ok': True, 'found': True, 'step_count': res['step_count'],
                'period_conflicts': len(res.get('period_conflicts', [])),
                'first': res['steps'][0]['spot'], 'last': res['steps'][-1]['spot']}
    if action == 'advice':
        return {'ok': True, 'found': res.get('found'), 'count': res.get('count'),
                'matched_specific': res.get('matched_specific'),
                'fallback_note': res.get('fallback_note')}
    return {'ok': True, 'found': res.get('found'), 'matches': len(res.get('matches', []))}


class ReActAgent:
    def __init__(self, tool=None, llm=None, max_steps=MAX_STEPS):
        self.tool = tool or KGQueryTool()
        self.llm = llm or LLMClient()
        self.max_steps = max_steps

    # ---------- 意图（LLM 可用时尝试，失败或非法回退规则版） ----------
    def _intent(self, query, trace):
        rules_intent = intent_mod.parse(query)
        source = 'rules'
        if self.llm.online:
            try:
                raw = self.llm.parse_intent(query)
                checked = self._validate_llm_intent(raw, rules_intent)
                rules_intent.update(checked)
                source = 'llm'
            except Exception as ex:
                trace.append({'step': len(trace) + 1, 'type': 'note',
                              'content': 'LLM 意图解析不可用，回退规则版：%s' % ex})
        trace.append({'step': len(trace) + 1, 'type': 'thought',
                      'content': '[%s] %s' % (source, self.llm.fallback.describe_intent(rules_intent)),
                      'intent_source': source})
        return rules_intent

    @staticmethod
    def _validate_llm_intent(raw, rules_intent):
        """只接受枚举/收录范围内的字段，其余保留规则值，避免模型编造景区。"""
        ok = {}
        allowed_scenic = {'黄山', '九寨沟', '张家界', None}
        if raw.get('scenic') in allowed_scenic:
            ok['scenic'] = raw['scenic']
        if raw.get('visitor_type') in {'老人', '亲子', '情侣', '普通'}:
            ok['visitor_type'] = raw['visitor_type']
        if raw.get('duration') in {1, 2}:
            ok['duration'] = int(raw['duration'])
        if isinstance(raw.get('preferences'), list):
            ok['preferences'] = [p for p in raw['preferences'] if isinstance(p, str)][:5]
        if isinstance(raw.get('constraints'), list):
            ok['constraints'] = [c for c in raw['constraints'] if isinstance(c, str)][:5]
        if isinstance(raw.get('need_clarification'), bool):
            ok['need_clarification'] = raw['need_clarification']
        # 模型给出的未收录景区名只在规则版没识别到景区时采纳
        if raw.get('unknown_scenic') and not rules_intent['scenic']:
            ok['unknown_scenic'] = str(raw['unknown_scenic'])[:10]
        return ok

    # ---------- 决策 ----------
    def _next_action(self, state):
        it = state['intent']
        obs = state['obs']
        if it.get('need_clarification'):
            return None
        if it.get('unknown_scenic') and not it['scenic']:
            if 'scenics' not in obs:
                return {'action': 'scenics', 'thought': '先查图谱收录了哪些景区，再据实说明未收录范围。'}
            return None
        if not it['scenic']:
            if 'scenics' not in obs:
                return {'action': 'scenics', 'thought': '未指定景区，先列出可用景区与路线规模。'}
            if 'route' not in obs:
                picked, rows, reason = planner.choose_scenic(obs['scenics']['scenics'], it)
                it['scenic'] = picked
                state['selection'] = {'ranking': rows, 'reason': reason}
                return {'action': 'route', 'args': {'scenic': picked},
                        'thought': '按图谱覆盖度择优 %s：%s 现在读取其路线步骤。' % (picked, reason)}
            return None
        if 'route' not in obs:
            return {'action': 'route', 'args': {'scenic': it['scenic']},
                    'thought': '读取 %s 的官方整理路线与时段状态。' % it['scenic']}
        if 'advice' not in obs:
            return {'action': 'advice', 'args': {'scenic': it['scenic'],
                                                'traveler_type': it['visitor_type'],
                                                'limit': 6},
                    'thought': '按“%s”类型取条件建议；无对应类型时接受通用建议并标注。' % it['visitor_type']}
        return None

    def _build_args(self, action, args):
        a = {'action': action}
        a.update(args or {})
        return a

    # ---------- 主循环 ----------
    def run(self, query):
        trace = []
        it = self._intent(query, trace)
        state = {'intent': it, 'obs': {}}
        tool_calls = []
        error_count = 0

        while len(tool_calls) < self.max_steps:
            decision = self._next_action(state)
            if not decision:
                break
            trace.append({'step': len(trace) + 1, 'type': 'thought', 'content': decision['thought']})
            args = self._build_args(decision['action'], decision.get('args'))
            trace.append({'step': len(trace) + 1, 'type': 'action',
                          'tool': TOOL_SPEC['name'], 'args': args})
            res = self.tool.run(args)
            tool_calls.append(args)
            if not res.get('ok'):
                error_count += 1
                trace.append({'step': len(trace) + 1, 'type': 'observation',
                              'content': '工具返回错误：%s' % res.get('error'), 'ok': False})
                # 错误处理：缺参数/未知 action 不重试，直接收敛为追问
                if '必须' in str(res.get('error')) or '未知 action' in str(res.get('error')):
                    it['need_clarification'] = True
                    it['flags'].append('工具参数缺失，Agent 停止扩展并转入追问。')
                    break
                state['obs'][decision['action']] = None
                continue
            state['obs'][decision['action']] = res
            digest = _obs_digest(decision['action'], res)
            trace.append({'step': len(trace) + 1, 'type': 'observation',
                          'content': json.dumps(digest, ensure_ascii=False), 'ok': True})
            if decision['action'] == 'route' and not res.get('found'):
                # 走了未收录分支，不再取建议
                state['obs']['advice'] = None
                break

        plan = planner.build(it, state['obs'], self.llm)
        if not plan.get('selection') and state.get('selection'):
            plan['selection'] = state['selection']
        trace.append({'step': len(trace) + 1, 'type': 'final',
                      'content': plan.get('summary', ''),
                      'scenic': plan.get('scenic'), 'found': plan.get('found'),
                      'evidence_count': len(plan.get('evidence_ids', []))})
        return {
            'query': query,
            'provider': self.llm.provider,
            'intent': it,
            'plan': plan,
            'traces': trace,
            'tool_calls': tool_calls,
            'tool_call_count': len(tool_calls),
            'error_count': error_count,
            'graph_sha256': self.tool.sha256,
        }
