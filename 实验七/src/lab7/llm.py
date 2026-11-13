"""LLM 后端：可切换 OpenAI 兼容接口 / 离线规则生成器。

- 配置 OPENAI_API_KEY 时，走 /chat/completions（标准库 urllib，不新增依赖）；
- 未配置或调用失败时回退 OfflineReasoner，仍能完整跑通 ReAct 闭环；
- provider 字段始终如实记录，报告与轨迹里不会把规则输出写成模型输出。
"""
from pathlib import Path
import json
import os
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = json.loads((ROOT / 'data/lab7/prompts.json').read_text(encoding='utf-8'))


def _load_dotenv(path):
    """Load simple KEY=VALUE entries without overriding process environment."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not key.isidentifier() or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ[key] = value


class LLMError(RuntimeError):
    pass


def _post_json(url, payload, headers, timeout):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _describe_request_error(ex):
    """Keep provider error codes useful for diagnosis without logging request secrets."""
    detail = '%s: %s' % (type(ex).__name__, ex)
    if isinstance(ex, urllib.error.HTTPError):
        try:
            raw = ex.read(4096).decode('utf-8', errors='replace')
            body = json.loads(raw)
            error = body.get('error', body) if isinstance(body, dict) else {}
            if isinstance(error, dict):
                code = error.get('code') or error.get('type')
                message = error.get('message')
                request_id = body.get('request_id') or body.get('requestId')
                extras = []
                if code:
                    extras.append('code=%s' % code)
                if request_id:
                    extras.append('request_id=%s' % request_id)
                if message:
                    extras.append('message=%s' % str(message)[:500])
                if extras:
                    detail += ' (' + '; '.join(extras) + ')'
        except (OSError, UnicodeError, ValueError):
            pass
    return detail


class OfflineReasoner:
    """确定性规则生成器：只复述规划器已核验的事实，不做自由创作。"""

    name = 'offline-rules'

    def describe_intent(self, it):
        parts = ['景区=%s' % (it['scenic'] or ('未收录:' + it['unknown_scenic'] if it['unknown_scenic'] else '未指定')),
                 '人群=%s' % it['visitor_type'],
                 '天数=%d' % it['duration']]
        if it['preferences']:
            parts.append('偏好=%s' % '、'.join(it['preferences']))
        if it['constraints']:
            parts.append('约束=%s' % '、'.join(it['constraints']))
        return '解析出 ' + '，'.join(parts) + '。'

    def compose(self, plan):
        if plan.get('need_clarification'):
            return plan.get('clarify_message') or '需要补充景区、人群和天数后才能规划。'
        if plan.get('found') is False:
            return plan.get('message') or '未能在图谱中生成方案。'
        if plan.get('answer_type') == 'entity':
            matches = (plan.get('answer_context') or {}).get('matches') or []
            if not matches:
                return plan.get('message') or '图谱中没有找到该实体。'
            rows = []
            for item in matches:
                stats = []
                if item.get('mention_count') is not None:
                    stats.append('提及 %s 次' % item['mention_count'])
                if item.get('document_count') is not None:
                    stats.append('涉及 %s 篇文档' % item['document_count'])
                rows.append('%s（%s%s）' % (item['label'], item['type'], '，' + '，'.join(stats) if stats else ''))
            return '图谱查询结果：' + '；'.join(rows) + '。'
        if plan.get('answer_type') == 'advice':
            if not plan.get('advices'):
                return plan.get('message') or '图谱中没有找到相关建议。'
            rows = ['（%s）%s' % (a['condition'], a['advice']) for a in plan['advices']]
            return '图谱中的历史材料建议：' + '；'.join(rows) + '。需核验当前服务与通行状态。'
        if plan.get('answer_type') == 'general':
            return plan.get('message') or '图谱景区清单暂不可用。'
        lines = []
        head = '%s · %s · %d 日方案（依据实验六图谱路线）' % (
            plan['scenic'], plan['visitor_type'], plan['duration'])
        lines.append(head + '。')
        for day in plan['days']:
            segs = []
            for sec in day['sections']:
                if not sec['steps']:
                    continue
                spots = '→'.join(s['spot'] for s in sec['steps'])
                segs.append('%s %s' % (sec['period'], spots))
            lines.append('第%d天：%s。' % (day['day'], '；'.join(segs)))
        if plan.get('period_note'):
            lines.append(plan['period_note'])
        if plan.get('advices'):
            lines.append('建议：' + '；'.join('（%s）%s' % (a['condition'], a['advice']) for a in plan['advices']) + '。')
        for w in plan.get('warnings', []):
            lines.append('注意：' + w)
        lines.append('以上景点均取自图谱步骤；顺序为上游文本顺序，未核验实际通行与当前开放状态。')
        return '\n'.join(lines)


class LLMClient:
    def __init__(self, timeout=None, force_offline=False):
        self.force_offline = force_offline
        if not force_offline:
            _load_dotenv(ROOT / '.env')
        self.api_key = '' if force_offline else os.environ.get('OPENAI_API_KEY', '').strip()
        self.base = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
        self.model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.timeout = timeout or int(os.environ.get('LLM_TIMEOUT', '30'))
        self.fallback = OfflineReasoner()
        self.provider = ('openai-compatible:%s' % self.model) if self.api_key else 'offline-rules'
        self.last_error = None
        self.request_attempts = 0
        self.successful_responses = 0
        self.failures = 0
        self.fallback_count = 0
        self.planning_attempts = 0
        self.planning_accepted = 0
        self.decision_attempts = 0
        self.decision_accepted = 0
        self.fallback_events = []

    def record_failure(self, error, fallback=True):
        self.failures += 1
        message = '%s: %s' % (type(error).__name__, error)
        if self.api_key:
            message = message.replace(self.api_key, '[REDACTED]')
        self.last_error = message
        if fallback:
            self.fallback_count += 1

    def record_fallback(self, error, failure_already_recorded=False, stage='unknown'):
        if not failure_already_recorded:
            self.failures += 1
        self.fallback_count += 1
        message = '%s: %s' % (type(error).__name__, error)
        if self.api_key:
            message = message.replace(self.api_key, '[REDACTED]')
        self.last_error = message
        self.fallback_events.append({'stage': stage, 'error': message})

    def diagnostics(self):
        return {
            'provider': self.provider,
            'force_offline': self.force_offline,
            'request_attempts': self.request_attempts,
            'successful_responses': self.successful_responses,
            'failures': self.failures,
            'fallback_count': self.fallback_count,
            'planning_attempts': self.planning_attempts,
            'planning_accepted': self.planning_accepted,
            'decision_attempts': self.decision_attempts,
            'decision_accepted': self.decision_accepted,
            'fallback_events': list(self.fallback_events),
            'last_error': self.last_error,
        }

    @property
    def online(self):
        return bool(self.api_key)

    # ---------- 底层调用 ----------
    def _chat(self, messages, temperature=0.2):
        if not self.api_key:
            raise LLMError('OPENAI_API_KEY 未配置')
        self.request_attempts += 1
        payload = {'model': self.model, 'messages': messages, 'temperature': temperature}
        try:
            data = _post_json(self.base + '/chat/completions', payload,
                              {'Content-Type': 'application/json',
                               'Authorization': 'Bearer ' + self.api_key}, self.timeout)
            content = data['choices'][0]['message']['content']
            if not isinstance(content, str):
                raise ValueError('choices[0].message.content 不是字符串')
            self.successful_responses += 1
            return content
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                KeyError, ValueError, TimeoutError) as ex:
            detail = _describe_request_error(ex)
            self.record_failure(LLMError(detail), fallback=False)
            raise LLMError(self.last_error) from ex

    # ---------- 意图 ----------
    def parse_intent(self, query):
        """有 key 时让模型给 JSON，再由调用方用规则结构校验；失败抛出 LLMError。"""
        if not self.online:
            raise LLMError('offline')
        try:
            content = self._chat([
                {'role': 'system', 'content': PROMPTS['intent_system']},
                {'role': 'user', 'content': PROMPTS['intent_user_template'].format(query=query)},
            ], temperature=0)
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as ex:
            self.record_failure(ex, fallback=False)
            raise LLMError('意图响应不是合法 JSON: %s' % ex) from ex

    # ---------- 受图谱约束的规划提案 ----------
    def plan_itinerary(self, query, plan):
        """Ask the model to assign graph-backed route steps to days and choose a pace.

        The planner validates this proposal before applying it. This method never
        lets model text add or remove route facts.
        """
        if not self.online:
            return None
        steps = []
        for day in plan.get('days', []):
            for section in day.get('sections', []):
                for step in section.get('steps', []):
                    steps.append({'order': step['order'], 'period': section['period'],
                                  'spot': step['spot'], 'activity': step.get('activity')})
        user_payload = {
            'query': query,
            'visitor_type': plan['visitor_type'],
            'duration': plan['duration'],
            'preferences': plan.get('preferences', []),
            'constraints': plan.get('constraints', []),
            'steps': steps,
        }
        before = self.failures
        self.planning_attempts += 1
        try:
            content = self._chat([
                {'role': 'system', 'content': PROMPTS['planning_system']},
                {'role': 'user', 'content': PROMPTS['planning_user_template'].format(
                    payload=json.dumps(user_payload, ensure_ascii=False))},
            ], temperature=0)
            proposal = json.loads(content)
            if not isinstance(proposal, dict):
                raise ValueError('规划响应必须是 JSON 对象')
            return proposal
        except (json.JSONDecodeError, TypeError, ValueError, LLMError) as ex:
            if self.failures == before:
                self.record_failure(ex, fallback=False)
            raise LLMError('规划提案不可用: %s' % ex) from ex

    def accept_planning(self):
        self.planning_accepted += 1

    # ---------- ReAct 工具决策 ----------
    def decide_action(self, query, intent, observations, history, tool_spec):
        """Select one next graph action from the live request and observed results."""
        if not self.online:
            return None
        self.decision_attempts += 1
        payload = {
            'query': query,
            'intent': {k: intent.get(k) for k in (
                'scenic', 'unknown_scenic', 'visitor_type', 'duration', 'preferences',
                'constraints', 'task_type', 'entity_name', 'need_clarification')},
            'observations': observations,
            'history': history,
            'tool_spec': tool_spec,
        }
        before = self.failures
        try:
            content = self._chat([
                {'role': 'system', 'content': PROMPTS['decision_system']},
                {'role': 'user', 'content': PROMPTS['decision_user_template'].format(
                    query=query, intent=json.dumps(payload['intent'], ensure_ascii=False),
                    observations=json.dumps(observations, ensure_ascii=False),
                    history=json.dumps(history, ensure_ascii=False),
                    tool_spec=json.dumps(tool_spec, ensure_ascii=False))},
            ], temperature=0)
            decision = json.loads(content)
            if not isinstance(decision, dict):
                raise ValueError('工具决策必须为 JSON 对象')
            return decision
        except (json.JSONDecodeError, TypeError, ValueError, LLMError) as ex:
            if self.failures == before:
                self.record_failure(ex, fallback=False)
            raise LLMError('工具决策不可用: %s' % ex) from ex

    def accept_decision(self):
        self.decision_accepted += 1

    # ---------- 生成 ----------
    def compose(self, plan):
        if not self.online or plan.get('need_clarification') or plan.get('found') is False:
            return self.fallback.compose(plan)
        try:
            content = self._chat([
                {'role': 'system', 'content': PROMPTS['final_system']},
                {'role': 'user', 'content': PROMPTS['final_user_template'].format(
                    query=plan.get('query', ''),
                    scenic=plan['scenic'], visitor_type=plan['visitor_type'],
                    duration=plan['duration'], steps=json.dumps(plan['days'], ensure_ascii=False),
                    advices=json.dumps(plan['advices'], ensure_ascii=False),
                    answer_context=json.dumps(plan.get('answer_context', {}), ensure_ascii=False),
                    warnings=json.dumps(plan['warnings'], ensure_ascii=False),
                    planning=json.dumps(plan.get('llm_planning') or {}, ensure_ascii=False))},
            ], temperature=0.3)
            return content.strip()
        except LLMError as ex:
            self.record_fallback(ex, failure_already_recorded=True, stage='final_answer')
            return self.fallback.compose(plan)
