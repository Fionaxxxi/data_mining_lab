"""生成实验七配图：Agent 架构、ReAct 轨迹、行程时段轴（PNG + SVG）。"""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/lab7'
FIG = OUT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)

for fp in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name(), 'DejaVu Sans']
        break
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False


def box(ax, x, y, w, h, text, fc, ec='#4a4a4a', fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.08',
                                fc=fc, ec=ec, lw=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=fs,
            fontweight='bold' if bold else 'normal', color='#1f1f1f', wrap=True)


def arrow(ax, xy1, xy2, style='-|>', ls='-', color='#5b6b7c'):
    ax.add_patch(FancyArrowPatch(xy1, xy2, arrowstyle=style, mutation_scale=12,
                                 lw=1.2, color=color, linestyle=ls,
                                 shrinkA=2, shrinkB=2))


def architecture():
    fig, ax = plt.subplots(figsize=(11.2, 6.4))
    ax.set_xlim(0, 11); ax.set_ylim(0, 6.4); ax.axis('off')
    ax.set_title('图1 旅游规划 Agent 架构（复用实验六图谱，不把图谱写进 Prompt）', fontsize=12, fontweight='bold')

    box(ax, 3.4, 5.5, 4.2, 0.62, '用户自然语言请求\n“带老人去黄山玩一天，希望轻松平缓”', '#e8f1fb', fs=9)
    box(ax, 3.3, 4.55, 3.95, 0.62, '意图解析器 intent.py\n景区 / 人群 / 天数 / 偏好 / 约束', '#e6f4ea', fs=9)
    box(ax, 2.6, 3.25, 5.8, 0.95,
        'ReAct 控制器 agent.py\nThought 决策 → Action 调工具 → Observation 读取 → 必要时再决策', '#fff4d6', fs=9, bold=True)
    box(ax, 0.35, 2.35, 2.7, 0.62, '工具 knowledge_graph_query\naction: scenics/route/advice/entity', '#fde8e8', fs=8.5)
    box(ax, 3.65, 2.35, 2.7, 0.62, '实验六图谱 graph.json\n471 节点 / 629 边 / 12 类关系', '#e9e6f7', fs=8.5)
    box(ax, 6.95, 2.35, 2.0, 0.62, '证据表 evidence.jsonl\n逐条 evidence_refs 追溯', '#e9e6f7', fs=8.5)
    box(ax, 1.9, 1.1, 3.1, 0.62, '规划器 planner.py\n时段消歧 / 择优 / 两日切分 / 回退', '#e6f4ea', fs=8.5)
    box(ax, 5.5, 1.1, 3.6, 0.62, '输出：结构化行程 JSON + 中文方案 + 轨迹\n（景点均回指图谱步骤）', '#e8f1fb', fs=8.5)
    box(ax, 7.6, 4.55, 3.05, 0.9,
        'LLM 后端 llm.py\nOPENAI_API_KEY → OpenAI 兼容 API\n未配置/失败 → 离线规则生成器\nprovider 如实记录', '#f2f2f2', fs=8, ec='#7a7a7a')

    arrow(ax, (5.5, 5.5), (5.5, 5.17))
    arrow(ax, (5.5, 4.55), (5.5, 4.2))
    arrow(ax, (4.1, 3.25), (2.0, 3.0))
    arrow(ax, (5.5, 3.25), (5.0, 3.0))
    arrow(ax, (2.0, 2.35), (4.4, 3.25), ls=':', color='#8a8a8a')
    arrow(ax, (6.0, 2.97), (6.0, 3.25), ls=':', color='#8a8a8a')
    arrow(ax, (5.0, 2.35), (3.6, 1.72))
    arrow(ax, (4.0, 1.1), (5.6, 1.1))
    arrow(ax, (8.4, 4.55), (7.4, 4.2), ls='--', color='#7a7a7a')
    ax.text(8.55, 4.05, '意图解析/润色', fontsize=7.5, color='#666666')

    ax.text(0.35, 0.55, '注：图谱以工具调用的方式按需查询；离线模式不调用模型，但 Thought→Action→Observation→Final 闭环与工具编排不变。',
            fontsize=7.8, color='#555555')
    for ext in ('png', 'svg'):
        fig.savefig(FIG / ('agent_architecture.' + ext), dpi=170, bbox_inches='tight')
    plt.close(fig)


def trace_demo():
    traces = [json.loads(x) for x in (OUT / 'traces.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
    demo = next(t for t in traces if t['id'] == 'family_jiuzhaigou')
    items = demo['traces']
    colors = {'thought': '#e6f4ea', 'action': '#fff4d6', 'observation': '#e8f1fb',
              'final': '#fde8e8', 'note': '#f2f2f2'}
    fig, ax = plt.subplots(figsize=(9.6, 0.62 * len(items) + 1.45))
    ax.set_xlim(0, 8.6); ax.set_ylim(0, len(items) * 0.62 + 1.0); ax.axis('off')
    ax.set_title('图2 典型用例 ReAct 轨迹（亲子·九寨沟·一日）', fontsize=12, fontweight='bold')
    top = len(items) * 0.62 + 0.7
    for i, t in enumerate(items):
        y = top - (i + 1) * 0.62
        typ = t['type']
        label = {'thought': 'THOUGHT', 'action': 'ACTION', 'observation': 'OBSERVATION',
                 'final': 'FINAL', 'note': 'NOTE'}.get(typ, typ.upper())
        ax.add_patch(FancyBboxPatch((0.15, y), 1.05, 0.44, boxstyle='round,pad=0.02,rounding_size=0.06',
                                    fc=colors.get(typ, '#ffffff'), ec='#9a9a9a', lw=0.8))
        ax.text(0.67, y + 0.22, label, ha='center', va='center', fontsize=8.5, fontweight='bold')
        if typ == 'action':
            txt = '%s %s' % (t.get('tool'), json.dumps(t.get('args'), ensure_ascii=False))
        else:
            txt = t.get('content', '')
        txt = txt.replace('\n', ' ')
        if len(txt) > 92:
            txt = txt[:89] + '…'
        ax.text(1.4, y + 0.22, txt, ha='left', va='center', fontsize=7.6, color='#222222')
    ax.text(0.15, 0.06, '说明：每次 ACTION 都是真实调用知识图谱工具，OBSERVATION 为其返回摘要；'
                       'FINAL 由规划器基于这些观察生成。', fontsize=7.4, color='#555555')
    for ext in ('png', 'svg'):
        fig.savefig(FIG / ('react_trace_demo.' + ext), dpi=170, bbox_inches='tight')
    plt.close(fig)


def plan_timeline():
    cases = json.loads((OUT / 'test_cases.json').read_text(encoding='utf-8'))
    demo = next(c for c in cases if c['id'] == 'family_jiuzhaigou')
    periods = ['上午', '中午', '下午']
    status_color = {'upstream_parse': '#3f7fbf',
                    'conflicting_hierarchy_heuristic': '#d9822b',
                    'order_monotonic_repair': '#8e6bb5'}
    status_name = {'upstream_parse': '上游解析',
                   'conflicting_hierarchy_heuristic': '层级推断（冲突，两值保留）',
                   'order_monotonic_repair': '时序单调修复'}
    fig, ax = plt.subplots(figsize=(11.5, 4.0))
    rows = {p: i for i, p in enumerate(periods)}
    for day in demo['days']:
        for sec in day['sections']:
            for st in sec['steps']:
                order = int(st.split()[0])
                spot = st.split(' ', 1)[1]
                status = spot.rsplit('(', 1)[-1].rstrip(')')
                spot = spot.rsplit('(', 1)[0].strip()
                y = rows.get(sec['period'], 3)
                ax.scatter(order, y, s=110, color=status_color.get(status, '#999999'), zorder=3,
                           edgecolor='white', linewidth=1.2)
                ax.annotate('%d %s' % (order, spot), (order, y), textcoords='offset points',
                            xytext=(0, 12), ha='center', fontsize=7.5)
    ax.set_yticks(list(rows.values()))
    ax.set_yticklabels(periods)
    ax.set_ylim(-0.6, 2.9)
    ax.set_xlim(0, 12.2)
    ax.set_xlabel('图谱路线步骤序号（九寨沟 11 步）')
    ax.set_title('图3 九寨沟一日行程的时段分布（颜色=时段状态来源）', fontsize=12, fontweight='bold')
    ax.grid(axis='x', linestyle=':', alpha=0.5)
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], marker='o', color='w', markerfacecolor=c, markersize=10, label=status_name[s])
               for s, c in status_color.items()]
    ax.legend(handles=handles, loc='upper left', fontsize=8, frameon=True, framealpha=0.95)
    fig.text(0.01, 0.015, '沟口在第1、11步重复出现（身份去重、步骤不去重）；'
                         '上游解析全部标“上午”，中午/下午由层级推断补位并保留冲突状态。',
             fontsize=7.8, color='#555555')
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    for ext in ('png', 'svg'):
        fig.savefig(FIG / ('plan_timeline.' + ext), dpi=170, bbox_inches='tight')
    plt.close(fig)


def main():
    architecture()
    trace_demo()
    plan_timeline()
    for f in sorted(FIG.glob('*')):
        print(f.name, f.stat().st_size)


if __name__ == '__main__':
    main()
