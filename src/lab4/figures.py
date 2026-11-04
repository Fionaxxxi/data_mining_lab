"""Create compact report figures from actual lab 4 outputs."""
import html
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs' / 'lab4'
fig = out / 'figures'
fig.mkdir(exist_ok=True)
full = json.loads((out / 'full_evaluation.json').read_text(encoding='utf8'))
examples = [next(x for x in full['cases'] if x['id'] == key) for key in ('HS-T02:604', 'ZJJ-T01:75')]


def svg(name, title, rows):
    height = 86 + len(rows) * 52
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}">',
             '<rect width="100%" height="100%" fill="#fff"/>',
             f'<text x="30" y="42" font-size="24" font-family="Microsoft YaHei, sans-serif" font-weight="bold">{html.escape(title)}</text>']
    for i, (label, value) in enumerate(rows):
        y = 88 + i * 52
        parts += [f'<rect x="20" y="{y-27}" width="960" height="44" fill="{("#eef4fa" if i % 2 == 0 else "#f8fafc")}"/>',
                  f'<text x="34" y="{y}" font-size="18" font-family="Microsoft YaHei, sans-serif">{html.escape(label)}</text>',
                  f'<text x="370" y="{y}" font-size="18" font-family="Microsoft YaHei, sans-serif">{html.escape(str(value))}</text>']
    parts.append('</svg>')
    (fig / name).write_text(''.join(parts), encoding='utf8')


svg('evaluation.svg', 'ʵ�����˹�����ͳ��', [('ԭ����������', '60'), ('����������б�', full['candidate_count']), ('��ȷ��ָ���ǹ�ָ', f"{full['status_counts']['resolved']} / {full['status_counts']['noncoref']}"), ('��ȷ������ָ', f"{full['status_counts']['uncertain']} / {full['status_counts']['cataphora']}"), ('���ж�������ȷ', f"{full['correct']} / {full['scored_count']} = {full['accuracy']:.1%}"), ('��ȷ��ָ����', f"{full['resolvable_covered']} / {full['resolvable_count']} = {full['resolvable_coverage']:.1%}")])
svg('resolution.svg', '��ָ��������֤', [('����', examples[0]['id']), ('ԭ�ľֲ�', '���ڵ��Ϲ����������ǻ�ɽ�ڶ��߷�'), ('�˹����д�', examples[0]['gold']), ('����Ԥ��', examples[0]['prediction']), ('�ж�', '��ȷ����Ӧԭ���ַ�λ�ÿ��� JSONL ����')])
svg('error.svg', 'ʣ������', [('����', examples[1]['id']), ('ԭ�ľֲ�', '�������żҽ����ξ�����������������������ɽ���'), ('�˹����д�', examples[1]['gold']), ('����Ԥ��', examples[1]['prediction']), ('ԭ��', '�����������Ȳ�һ�£�����ȷ�ַ�����Ϊ����')])
