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
        if rules_intent.get('task_type') == 'entity' and rules_intent.get('scenic'):
            candidates = []
            for node in self.tool.nodes.values():
                if node.get('scenic') != rules_intent['scenic'] or node.get('type') in {'Scenic', 'Step'}:
                    continue
                for name in [node.get('label')] + list(node.get('aliases') or []):
                    if name and name in query:
                        candidates.append(name)
            if candidates:
                rules_intent['entity_name'] = max(candidates, key=len)
        source = 'rules'
        if self.llm.online:
            failures_before = self.llm.failures
            try:
                raw = self.llm.parse_intent(query)
                checked = self._validate_llm_intent(raw, rules_intent, query=query)
                rules_intent.update(checked)
                source = 'llm'
            except Exception as ex:
                self.llm.record_fallback(ex, failure_already_recorded=self.llm.failures > failures_before,
                                         stage='intent')
                trace.append({'step': len(trace) + 1, 'type': 'note',
                              'content': 'LLM 意图解析不可用，回退规则版：%s' % ex})
        trace.append({'step': len(trace) + 1, 'type': 'thought',
                      'content': '[%s] %s' % (source, self.llm.fallback.describe_intent(rules_intent)),
                      'intent_source': source})
        return rules_intent

    @staticmethod
    def _validate_llm_intent(raw, rules_intent, query=''):
        """只接受枚举/收录范围内的字段，其余保留规则值，避免模型编造景区。"""
        if not isinstance(raw, dict):
            raise ValueError('LLM 意图必须是 JSON 对象')
        ok = {}
        allowed_scenic = {'黄山', '九寨沟', '张家界', None}
        # 用户明确给出的景区或未收录景区优先，模型不得清空或改成另一处。
        if not rules_intent['scenic'] and not rules_intent['unknown_scenic'] and raw.get('scenic') in allowed_scenic:
            ok['scenic'] = raw['scenic']
        raw_visitor = raw.get('visitor_type')
        if (rules_intent['visitor_type'] == '普通' and isinstance(raw_visitor, str)
                and raw_visitor in {'老人', '亲子', '情侣', '普通'}):
            ok['visitor_type'] = raw['visitor_type']
        raw_duration = raw.get('duration')
        if (not rules_intent['duration_explicit'] and not isinstance(raw_duration, bool)
                and isinstance(raw_duration, (int, str)) and str(raw_duration) in {'1', '2'}):
            ok['duration'] = int(raw_duration)
        if isinstance(raw.get('preferences'), list):
            ok['preferences'] = list(dict.fromkeys(rules_intent['preferences'] +
                [p for p in raw['preferences'] if isinstance(p, str)]))[:5]
        if isinstance(raw.get('constraints'), list):
            ok['constraints'] = list(dict.fromkeys(rules_intent['constraints'] +
                [c for c in raw['constraints'] if isinstance(c, str)]))[:5]
        raw_task_type = raw.get('task_type')
        if (rules_intent.get('task_type', 'route') == 'route'
                and isinstance(raw_task_type, str)
                and raw_task_type in {'route', 'advice', 'entity', 'general'}):
            ok['task_type'] = raw_task_type
        entity_name = raw.get('entity_name')
        if isinstance(entity_name, str) and entity_name and entity_name in query and len(entity_name) <= 80:
            ok['entity_name'] = entity_name
        # Clarification is a business gate: the model may enrich fields, but cannot
        # turn a sufficiently specified request into a clarification-only result.
        # 模型给出的未收录景区名只在规则版没识别到景区时采纳
        if raw.get('unknown_scenic') and not rules_intent['scenic']:
            ok['unknown_scenic'] = str(raw['unknown_scenic'])[:10]
        return ok

    @staticmethod
    def _required_actions(state):
        it, obs = state['intent'], state['obs']
        if it.get('need_clarification'):
            return []
        task = it.get('task_type', 'route')
        if task == 'general':
            return [] if 'scenics' in obs else ['scenics']
        if it.get('unknown_scenic'):
            return [] if 'scenics' in obs else ['scenics']
        if task == 'entity':
            return [] if not it.get('scenic') or not it.get('entity_name') or 'entity' in obs else ['entity']
        if task == 'advice':
            if not it.get('scenic'):
                return ['advice'] if 'scenics' in obs else ['scenics']
            return [] if 'advice' in obs else ['advice']
        actions = []
        if not it.get('scenic'):
            if 'scenics' not in obs:
                return ['scenics']
            if not state.get('intent', {}).get('scenic'):
                actions.append('route')
        elif 'route' not in obs:
            actions.append('route')
        route = obs.get('route')
        needs_advice = (it.get('visitor_type') != '普通' or it.get('constraints')
                        or it.get('preferences'))
        if route and route.get('found') and needs_advice and 'advice' not in obs:
            actions.append('advice')
        return actions

    @staticmethod
    def _decision_observations(state):
        result = {}
        for action, obs in state['obs'].items():
            if not isinstance(obs, dict):
                result[action] = {'ok': False, 'error': '工具调用未成功'}
            elif action == 'route':
                result[action] = {
                    'ok': obs.get('ok'), 'found': obs.get('found'), 'scenic': obs.get('scenic'),
                    'step_count': obs.get('step_count'), 'steps': [
                        {'order': s.get('order'), 'spot': s.get('spot'), 'activity': s.get('activity'),
                         'periods': [p.get('label') for p in s.get('periods', [])]}
                        for s in obs.get('steps', [])],
                    'evidence_refs': obs.get('route_evidence_refs', [])[:6],
                }
            elif action == 'advice':
                result[action] = {
                    'ok': obs.get('ok'), 'found': obs.get('found'),
                    'advices': [{'condition': a.get('condition'), 'advice': a.get('advice'),
                                 'evidence_refs': a.get('evidence_refs', [])[:3]}
                                for a in obs.get('advices', [])],
                    'fallback_note': obs.get('fallback_note'),
                }
            elif action == 'entity':
                result[action] = obs
            else:
                result[action] = {'ok': obs.get('ok'), 'scenics': obs.get('scenics', []),
                                  'available': obs.get('available')}
        return result

    def _validate_action_decision(self, decision, state, query):
        if not isinstance(decision, dict):
            raise ValueError('工具决策必须是 JSON 对象')
        if set(decision) - {'action', 'args', 'reason'}:
            raise ValueError('工具决策包含额外字段')
        action, args, reason = decision.get('action'), decision.get('args', {}), decision.get('reason', '')
        if action not in {'scenics', 'route', 'advice', 'entity', 'stop'} or not isinstance(args, dict):
            raise ValueError('action 或 args 不符合决策契约')
        if not isinstance(reason, str) or len(reason) > 240:
            raise ValueError('reason 必须是 240 字以内的字符串')
        needed = self._required_actions(state)
        if action == 'stop':
            if args:
                raise ValueError('stop 不接受参数')
            if needed:
                raise ValueError('仍需查询 %s，不能提前结束' % '、'.join(needed))
            return {'action': 'stop', 'args': {}, 'reason': reason or '当前信息足以回答。'}
        if action not in needed:
            raise ValueError('当前问题/工具观察不需要 action=%s；待处理=%s' % (action, needed))
        if action in state['obs']:
            raise ValueError('拒绝重复调用 action=%s' % action)

        it = state['intent']
        known = set((state['obs'].get('scenics') or {}).get('available', []))
        if action == 'scenics':
            # The list query takes no parameters. Ignore model-added context fields;
            # they cannot affect the read-only tool call.
            args = {}
        elif action == 'route':
            if 'scenic' not in args and it.get('scenic'):
                args = {'scenic': it['scenic']}
            else:
                args = {'scenic': args.get('scenic')} if 'scenic' in args else args
            if set(args) != {'scenic'}:
                raise ValueError('route 必须提供 scenic')
            scenic = args['scenic']
            if not isinstance(scenic, str) or len(scenic) > 40:
                raise ValueError('route scenic 格式无效')
            if it.get('unknown_scenic') or (it.get('scenic') and scenic != it['scenic']):
                raise ValueError('route scenic 与用户明确景区冲突')
            if not it.get('scenic') and scenic not in known:
                raise ValueError('route scenic 不在图谱收录清单中')
            if not it.get('scenic'):
                it['scenic'] = scenic
                _, ranking, default_reason = planner.choose_scenic(
                    state['obs']['scenics']['scenics'], it)
                state['selection'] = {'ranking': ranking,
                                      'reason': 'LLM 根据问题选择 %s：%s（候选已限定为图谱收录景区）。'
                                      % (scenic, reason or default_reason)}
        elif action == 'advice':
            # Drop fields outside the tool contract before validating the remaining
            # values. The model cannot pass these fields to KGQueryTool.
            args = {k: v for k, v in args.items()
                    if k in {'scenic', 'traveler_type', 'contains', 'limit'}}
            scenic = args.get('scenic', it.get('scenic'))
            if it.get('scenic') is None and scenic in known and not it.get('unknown_scenic'):
                it['scenic'] = scenic
                _, ranking, default_reason = planner.choose_scenic(
                    state['obs']['scenics']['scenics'], it)
                state['selection'] = {'ranking': ranking,
                                      'reason': 'LLM 根据问题选择 %s：%s（候选已限定为图谱收录景区）。'
                                      % (scenic, reason or default_reason)}
            if scenic != it.get('scenic'):
                raise ValueError('advice scenic 必须匹配已选景区')
            traveler = args.get('traveler_type', it.get('visitor_type'))
            if traveler not in {'老人', '亲子', '情侣', '普通'} or traveler != it.get('visitor_type'):
                raise ValueError('advice traveler_type 与已解析人群冲突')
            contains = args.get('contains')
            if contains is not None and (not isinstance(contains, str) or len(contains) > 40
                                         or contains not in query):
                raise ValueError('advice contains 必须是用户原话中的关键词')
            limit = args.get('limit', 6)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 6:
                raise ValueError('advice limit 必须是 1–6 的整数')
            args = {'scenic': scenic, 'traveler_type': traveler, 'limit': limit}
            if contains:
                args['contains'] = contains
        elif action == 'entity':
            if set(args) != {'scenic', 'name'}:
                raise ValueError('entity 必须提供 scenic 和 name')
            scenic, name = args['scenic'], args['name']
            if scenic != it.get('scenic') or scenic not in {'黄山', '九寨沟', '张家界'}:
                raise ValueError('entity scenic 必须是用户明确指出的已收录景区')
            if not isinstance(name, str) or not name or len(name) > 80 or name not in query:
                raise ValueError('entity name 必须来自用户原话中的实体名称')
            if it.get('entity_name') and name != it['entity_name']:
                raise ValueError('entity name 与已解析实体不一致')
        return {'action': action, 'args': args, 'reason': reason or '根据用户问题选择图谱查询。'}

    # ---------- 决策 ----------
    def _next_action(self, state):
        it = state['intent']
        obs = state['obs']
        if it.get('need_clarification'):
            return None
        if it.get('task_type') == 'entity':
            if it.get('scenic') and it.get('entity_name') and 'entity' not in obs:
                return {'action': 'entity', 'args': {'scenic': it['scenic'], 'name': it['entity_name']},
                        'thought': '用户询问实体事实，按指定景区和名称读取图谱实体记录。'}
            return None
        if it.get('task_type') == 'advice':
            if it.get('scenic') and 'advice' not in obs:
                return {'action': 'advice', 'args': {'scenic': it['scenic'],
                                                    'traveler_type': it['visitor_type'], 'limit': 6},
                        'thought': '用户单独询问建议，按景区和已解析人群查询条件建议。'}
            return None
        if it.get('task_type') == 'general':
            if 'scenics' not in obs:
                return {'action': 'scenics', 'thought': '用户询问收录范围，查询图谱景区清单。'}
            return None
        if it.get('unknown_scenic') and not it['scenic']:
            if 'scenics' not in obs:
                return {'action': 'scenics', 'thought': '先查图谱收录了哪些景区，再据实说明未收录范围。'}
            return None
        if not it['scenic']:
            if 'scenics' not in obs:
                return {'action': 'scenics', 'thought': '未指定景区，先列出可用景区与路线规模。'}
            if 'route' not in obs and 'advice' not in obs:
                picked, rows, reason = planner.choose_scenic(obs['scenics']['scenics'], it)
                it['scenic'] = picked
                state['selection'] = {'ranking': rows, 'reason': reason}
                if it.get('task_type') == 'advice':
                    return {'action': 'advice', 'args': {'scenic': picked,
                                                        'traveler_type': it['visitor_type'], 'limit': 6},
                            'thought': '按图谱候选与用户条件择优后查询相关建议。'}
                return {'action': 'route', 'args': {'scenic': picked},
                        'thought': '按图谱覆盖度择优 %s：%s 现在读取其路线步骤。' % (picked, reason)}
            return None
        if 'route' not in obs and it.get('task_type') != 'advice':
            return {'action': 'route', 'args': {'scenic': it['scenic']},
                    'thought': '读取 %s 的官方整理路线与时段状态。' % it['scenic']}
        if 'advice' not in obs and (it.get('task_type') == 'advice' or
                                    it['visitor_type'] != '普通' or it.get('constraints') or
                                    it.get('preferences')):
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
        action_history = []
        error_count = 0

        decision_turns = 0
        while len(tool_calls) < self.max_steps:
            needed = self._required_actions(state)
            should_decide = bool(needed) or ((it.get('need_clarification') or
                             (it.get('task_type') == 'entity' and not it.get('entity_name')))
                             and decision_turns == 0)
            if not should_decide:
                break
            decision_turns += 1
            decision = None
            source = 'rules'
            if self.llm.online:
                failures_before = self.llm.failures
                try:
                    proposal = self.llm.decide_action(
                        query, it, self._decision_observations(state),
                        action_history, TOOL_SPEC)
                    decision = self._validate_action_decision(proposal, state, query)
                    self.llm.accept_decision()
                    source = 'llm'
                except Exception as ex:
                    self.llm.record_fallback(ex, failure_already_recorded=self.llm.failures > failures_before,
                                             stage='decision')
                    trace.append({'step': len(trace) + 1, 'type': 'note',
                                  'content': 'LLM 工具决策不可用，回退规则决策：%s' % ex})
            if decision is None:
                decision = self._next_action(state)
            if not decision:
                break
            if decision['action'] == 'stop':
                trace.append({'step': len(trace) + 1, 'type': 'thought',
                              'content': '[%s] 停止图谱查询：%s' % (source, decision['reason']),
                              'decision_source': source, 'decision': 'stop'})
                break
            trace.append({'step': len(trace) + 1, 'type': 'thought',
                          'content': '[%s] %s' % (source, decision.get('reason') or decision.get('thought', '调用图谱工具。')),
                          'decision_source': source, 'decision': decision['action']})
            args = self._build_args(decision['action'], decision.get('args'))
            trace.append({'step': len(trace) + 1, 'type': 'action',
                          'tool': TOOL_SPEC['name'], 'args': args})
            res = self.tool.run(args)
            tool_calls.append(args)
            action_history.append({'action': decision['action'], 'args': args,
                                   'ok': bool(res.get('ok')), 'observation': _obs_digest(decision['action'], res)})
            if not res.get('ok'):
                error_count += 1
                trace.append({'step': len(trace) + 1, 'type': 'observation',
                              'content': '工具返回错误：%s' % res.get('error'), 'ok': False})
                state['obs'][decision['action']] = res
                continue
            state['obs'][decision['action']] = res
            digest = _obs_digest(decision['action'], res)
            trace.append({'step': len(trace) + 1, 'type': 'observation',
                          'content': json.dumps(digest, ensure_ascii=False), 'ok': True})
            if decision['action'] == 'route' and not res.get('found'):
                # 走了未收录分支，不再取建议
                state['obs']['advice'] = None
                break

        events_before = len(self.llm.fallback_events)
        plan = planner.build(it, state['obs'], self.llm, query=query)
        if not plan.get('selection') and state.get('selection'):
            plan['selection'] = state['selection']
        for event in self.llm.fallback_events[events_before:]:
            stage = event.get('stage', 'unknown')
            if stage == 'planning':
                message = 'LLM 规划提案未通过，已使用规则计划：%s' % event.get('error')
            elif stage == 'final_answer':
                message = 'LLM 最终回答生成失败，已回退规则版：%s' % event.get('error')
            else:
                message = 'LLM %s 阶段失败，已安全回退：%s' % (stage, event.get('error'))
            trace.append({'step': len(trace) + 1, 'type': 'note',
                          'content': message})
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
            'llm': self.llm.diagnostics(),
        }
