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


class LLMError(RuntimeError):
    pass


def _post_json(url, payload, headers, timeout):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


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
    def __init__(self, timeout=None):
        self.api_key = os.environ.get('OPENAI_API_KEY', '').strip()
        self.base = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
        self.model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.timeout = timeout or int(os.environ.get('LLM_TIMEOUT', '30'))
        self.fallback = OfflineReasoner()
        self.provider = ('openai-compatible:%s' % self.model) if self.api_key else 'offline-rules'
        self.last_error = None

    @property
    def online(self):
        return bool(self.api_key)

    # ---------- 底层调用 ----------
    def _chat(self, messages, temperature=0.2):
        if not self.api_key:
            raise LLMError('OPENAI_API_KEY 未配置')
        payload = {'model': self.model, 'messages': messages, 'temperature': temperature}
        try:
            data = _post_json(self.base + '/chat/completions', payload,
                              {'Content-Type': 'application/json',
                               'Authorization': 'Bearer ' + self.api_key}, self.timeout)
            return data['choices'][0]['message']['content']
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as ex:
            raise LLMError('%s: %s' % (type(ex).__name__, ex)) from ex

    # ---------- 意图 ----------
    def parse_intent(self, query):
        """有 key 时让模型给 JSON，再由调用方用规则结构校验；失败抛出 LLMError。"""
        if not self.online:
            raise LLMError('offline')
        content = self._chat([
            {'role': 'system', 'content': PROMPTS['intent_system']},
            {'role': 'user', 'content': PROMPTS['intent_user_template'].format(query=query)},
        ], temperature=0)
        return json.loads(content)

    # ---------- 生成 ----------
    def compose(self, plan):
        if not self.online or plan.get('need_clarification') or plan.get('found') is False:
            return self.fallback.compose(plan)
        try:
            content = self._chat([
                {'role': 'system', 'content': PROMPTS['final_system']},
                {'role': 'user', 'content': PROMPTS['final_user_template'].format(
                    scenic=plan['scenic'], visitor_type=plan['visitor_type'],
                    duration=plan['duration'], steps=json.dumps(plan['days'], ensure_ascii=False),
                    advices=json.dumps(plan['advices'], ensure_ascii=False),
                    warnings=json.dumps(plan['warnings'], ensure_ascii=False))},
            ], temperature=0.3)
            return content.strip()
        except LLMError as ex:
            self.last_error = str(ex)
            return self.fallback.compose(plan)
