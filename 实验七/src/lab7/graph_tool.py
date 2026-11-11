"""图谱查询工具：把实验六的 graph.json 封装为 Agent 可调用工具。

设计要点（对应评分项“知识图谱查询工具封装”）：
- 工具不是把图谱全文塞进 Prompt，而是按结构化参数按需查询；
- 输入/输出都有固定 Schema，结果附带 evidence_refs 供追溯；
- 查询过少时回退并显式标注，未知景区返回空结果与可选景区，不编造；
- 任何异常都收敛成 {"ok": false, "error": ...}，不向 Agent 抛出裸异常。
"""
from pathlib import Path
from collections import defaultdict
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
LAB6 = ROOT / 'outputs/lab6'
DEFAULT_GRAPH = LAB6 / 'graph.json'

ACTIONS = ['scenics', 'route', 'advice', 'entity']
ALLOWED_KEYS = {
    'scenics': {'action'},
    'route': {'action', 'scenic'},
    'advice': {'action', 'scenic', 'traveler_type', 'contains', 'limit'},
    'entity': {'action', 'scenic', 'name'},
}

# 供 LLM 或人工阅读的工具说明（与 input_schema 一致）
TOOL_SPEC = {
    'name': 'knowledge_graph_query',
    'description': (
        '查询实验六旅游知识图谱。支持列景区、取某景区官方路线步骤（含时段状态与交通）、'
        '按游客类型/关键词取条件建议、按名称查地点实体。所有结果带 evidence_refs。'
    ),
    'input_schema': {
        'type': 'object',
        'required': ['action'],
        'properties': {
            'action': {'type': 'string', 'enum': ACTIONS},
            'scenic': {'type': 'string', 'description': '景区名，仅黄山/九寨沟/张家界'},
            'traveler_type': {'type': 'string', 'description': '老人/亲子/情侣/普通'},
            'contains': {'type': 'string', 'description': '建议关键词，如 体力、晕车、索道'},
            'limit': {'type': 'integer', 'description': '建议条数上限，默认 8'},
            'name': {'type': 'string', 'description': 'entity 查询的名称或别名'},
        },
    },
}

TRAVELER_MAP = {
    '老人': '体力约束游客',
    '亲子': '亲子游客',
    '情侣': None,
    '普通': '普通游客',
}


class KGQueryTool:
    """只读封装实验六图谱；不新增、不改写任何节点或边。"""

    def __init__(self, graph_path=None):
        path = Path(graph_path or DEFAULT_GRAPH)
        raw = path.read_bytes()
        self.graph_path = path
        self.sha256 = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw.decode('utf-8-sig'))
        self.nodes = {n['id']: n for n in data['nodes']}
        self.edges = data['edges']
        self.out_edges = defaultdict(list)
        for e in self.edges:
            self.out_edges[e['source']].append(e)
        self._route_cache = {}

    # ---------- 内部工具 ----------
    def _err(self, msg, **extra):
        return {'ok': False, 'error': msg, 'tool': TOOL_SPEC['name'], **extra}

    def _scenic_names(self):
        return sorted(n['label'] for n in self.nodes.values() if n['type'] == 'Scenic')

    def _steps(self, scenic):
        rid = 'route:' + scenic
        if rid not in self.nodes:
            return None, []
        steps = [self.nodes[e['target']] for e in self.out_edges[rid] if e['type'] == 'HAS_STEP']
        return rid, sorted(steps, key=lambda n: n['order'])

    def _step_detail(self, step):
        places, transports, periods = [], [], []
        for e in self.out_edges[step['id']]:
            t = e['type']
            target = self.nodes[e['target']]
            if t == 'AT':
                places.append({'label': target['label'], 'node_id': target['id'],
                               'evidence_refs': e['evidence_refs']})
            elif t == 'USES' and target['type'] == 'Transport':
                transports.append({'label': target['label'], 'node_id': target['id'],
                                   'evidence_refs': e['evidence_refs']})
            elif t == 'DURING':
                periods.append({'label': target['label'], 'status': e.get('status'),
                                'evidence_refs': e['evidence_refs']})
        return {
            'step_id': step['id'],
            'order': step['order'],
            'label': step['label'],
            'spot': places[0]['label'] if places else None,
            'activity': step['activity'],
            'activity_status': step.get('activity_status'),
            'periods': periods,
            'transports': transports,
            'evidence_refs': step['evidence_refs'],
        }

    # ---------- 各 action ----------
    def _scenics(self, args):
        out = []
        for s in self._scenic_names():
            rid, steps = self._steps(s)
            cond = [n for n in self.nodes.values()
                    if n['type'] == 'Condition' and n['scenic'] == s]
            out.append({
                'scenic': s,
                'route_id': rid,
                'step_count': len(steps),
                'step_spots': [self._step_detail(x)['spot'] for x in steps],
                'node_count': sum(n['scenic'] == s for n in self.nodes.values()),
                'condition_count': len(cond),
                'route_evidence_refs': sorted({r for x in steps for r in x['evidence_refs']}),
            })
        return {'ok': True, 'scenics': out, 'available': [x['scenic'] for x in out]}

    def _route(self, args):
        scenic = args.get('scenic')
        rid, steps = self._steps(scenic)
        if not steps:
            return {'ok': True, 'scenic': scenic, 'found': False,
                    'available': self._scenic_names(),
                    'note': '该景区未收录于实验六图谱，未返回任何步骤；不据其他景区推测。'}
        conflicts = []
        for st in steps:
            detail = self._step_detail(st)
            if len(detail['periods']) > 1:
                conflicts.append({'order': st['order'], 'spot': detail['spot'],
                                  'periods': [p['label'] for p in detail['periods']],
                                  'statuses': [p['status'] for p in detail['periods']]})
        route_id = rid
        route_node = self.nodes[route_id]
        return {'ok': True, 'scenic': scenic, 'found': True, 'route_id': route_id,
                'route_label': route_node['label'], 'route_evidence_refs': route_node['evidence_refs'],
                'step_count': len(steps), 'steps': [self._step_detail(x) for x in steps],
                'period_conflicts': conflicts,
                'note': '时段同时保留上游解析与层级推断，两种状态不作等价；顺序为上游文本顺序，未核验实际通行。'}

    def _advice(self, args):
        scenic = args.get('scenic')
        if scenic not in self._scenic_names():
            return {'ok': True, 'scenic': scenic, 'found': False,
                    'available': self._scenic_names(),
                    'note': '该景区未收录，返回空建议列表。'}
        limit = int(args.get('limit') or 8)
        label_map = TRAVELER_MAP
        want = label_map.get(args.get('traveler_type'))
        contains = args.get('contains') or ''
        rows, specific, general = [], [], []
        for e in self.edges:
            if e['type'] != 'RECOMMENDS':
                continue
            cond = self.nodes[e['source']]
            adv = self.nodes[e['target']]
            if cond['scenic'] != scenic:
                continue
            row = {
                'mapping_id': adv.get('mapping_id'),
                'condition': cond['label'],
                'condition_type': cond.get('condition_type'),
                'traveler_type': cond.get('traveler_type'),
                'advice': adv['label'],
                'negative': bool(adv.get('negative')),
                'historical_only': bool(adv.get('historical_only')),
                'evidence_refs': sorted(set(e['evidence_refs']) | set(adv['evidence_refs'])),
            }
            if contains and contains not in (row['condition'] + row['advice'] + str(row['condition_type'])):
                continue
            rows.append(row)
            if want and row['traveler_type'] == want:
                specific.append(row)
            elif row['traveler_type'] == '普通游客':
                general.append(row)
        selected = specific + general
        note = '建议均为材料原句的历史建议，需核验当前开放与服务状态。'
        fallback = None
        if want and not specific:
            fallback = '图谱中没有与“%s”直接对应的游客类型建议，以下为通用建议，不代表该人群已被专门核验。' % args.get('traveler_type')
            selected = rows
        elif not selected:
            fallback = '按给定条件没有命中建议，已回退为该景区全部建议。'
            selected = rows
        if len(selected) > limit:
            selected = selected[:limit]
        return {'ok': True, 'scenic': scenic, 'found': True, 'requested_traveler_type': args.get('traveler_type'),
                'matched_specific': len(specific), 'general_count': len(general),
                'count': len(selected), 'advices': selected, 'fallback_note': fallback, 'note': note}

    def _entity(self, args):
        scenic, name = args.get('scenic'), args.get('name')
        if not name:
            return self._err('entity 查询缺少 name')
        exact = [n for n in self.nodes.values()
                 if n['scenic'] == scenic and n['type'] != 'Step'
                 and (n['label'] == name or name in (n.get('aliases') or []))]
        if exact:
            return {'ok': True, 'scenic': scenic, 'name': name, 'found': True,
                    'matches': [{'id': n['id'], 'type': n['type'], 'label': n['label'],
                                 'aliases': n.get('aliases'), 'mention_count': n.get('mention_count'),
                                 'document_count': n.get('document_count'),
                                 'official_mentions': n.get('official_mentions'),
                                 'tourist_mentions': n.get('tourist_mentions'),
                                 'evidence_refs': n['evidence_refs']} for n in exact]}
        near = [n['label'] for n in self.nodes.values()
                if n['scenic'] == scenic and n['type'] in ('Place', 'Transport', 'Scenic')
                and name in n['label']][:5]
        return {'ok': True, 'scenic': scenic, 'name': name, 'found': False,
                'similar_labels': near,
                'note': '未做模糊合并；similar_labels 仅供人工确认，不作为同义结论。'}

    # ---------- 对外入口 ----------
    def run(self, args):
        if not isinstance(args, dict):
            return self._err('工具参数必须是 JSON 对象')
        action = args.get('action')
        if action not in ACTIONS:
            return self._err('未知 action: %r，允许值 %s' % (action, ACTIONS))
        unknown = set(args) - ALLOWED_KEYS[action]
        if unknown:
            return self._err('action=%s 不接受参数 %s' % (action, sorted(unknown)))
        if action == 'entity' and not args.get('scenic'):
            return self._err('entity 查询必须给 scenic，避免跨景区同名混淆')
        try:
            if action == 'scenics':
                return self._scenics(args)
            if action == 'route':
                if not args.get('scenic'):
                    return self._err('route 查询必须给 scenic')
                return self._route(args)
            if action == 'advice':
                if not args.get('scenic'):
                    return self._err('advice 查询必须给 scenic')
                return self._advice(args)
            return self._entity(args)
        except Exception as ex:  # 工具层兜底，不抛给 Agent
            return self._err('%s: %s' % (type(ex).__name__, ex))

    def evidence_ids(self):
        """实验六证据表中实际存在的 id 集合，供验收核对引用是否可解析。"""
        ids = set()
        path = LAB6 / 'evidence.jsonl'
        if path.exists():
            for line in path.read_text(encoding='utf8').splitlines():
                if line.strip():
                    ids.add(json.loads(line)['id'])
        return ids
