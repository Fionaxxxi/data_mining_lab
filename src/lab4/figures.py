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


svg('evaluation.svg', '实验四人工核验统计', [('原文正则命中', '60'), ('进入待消解列表', full['candidate_count']), ('明确共指／非共指', f"{full['status_counts']['resolved']} / {full['status_counts']['noncoref']}"), ('不确定／后指', f"{full['status_counts']['uncertain']} / {full['status_counts']['cataphora']}"), ('可判定样本正确', f"{full['correct']} / {full['scored_count']} = {full['accuracy']:.1%}"), ('明确共指覆盖', f"{full['resolvable_covered']} / {full['resolvable_count']} = {full['resolvable_coverage']:.1%}")])
svg('resolution.svg', '共指消解结果例证', [('样本', examples[0]['id']), ('原文局部', '终于登上光明顶，它是黄山第二高峰'), ('人工先行词', examples[0]['gold']), ('规则预测', examples[0]['prediction']), ('判定', '正确；对应原文字符位置可在 JSONL 核验')])
svg('error.svg', '剩余误差案例', [('样本', examples[1]['id']), ('原文局部', '赴湖南张家界旅游景区游览……饱览了那里奇山异峰'), ('人工先行词', examples[1]['gold']), ('规则预测', examples[1]['prediction']), ('原因', '景区名称粒度不一致；按精确字符串计为错误')])
