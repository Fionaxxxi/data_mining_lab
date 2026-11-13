"""把本次真实测试输出的关键行绘制为可插入报告的 SVG。"""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/lab7'
FIG = OUT / 'figures'


def render(source, target, title, keep):
    lines = source.read_text(encoding='utf-8-sig').splitlines()
    selected = [line for line in lines if keep(line)]
    width, gap, line_height = 1700, 72, 34
    height = gap + line_height * (len(selected) + 2)
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            f'<rect width="100%" height="100%" fill="#17202b"/>',
            f'<text x="32" y="48" fill="#f4f7fb" font-family="Microsoft YaHei, sans-serif" font-size="27" font-weight="bold">{escape(title)}</text>']
    for i, line in enumerate(selected):
        color = '#8de0a3' if line.startswith('PASS') or '通过' in line else '#edf3fa'
        body.append(f'<text x="32" y="{gap + (i + 1) * line_height}" fill="{color}" '
                    f'font-family="Microsoft YaHei, sans-serif" font-size="20">{escape(line[:150])}</text>')
    body.append('</svg>')
    target.write_text('\n'.join(body) + '\n', encoding='utf-8')
    return len(selected)


if __name__ == '__main__':
    FIG.mkdir(parents=True, exist_ok=True)
    n1 = render(OUT / 'console_tests.txt', FIG / 'console_tests.svg',
                '实验七场景测试：实际终端输出摘录',
                lambda s: s.startswith('实验七') or s.startswith('[') or '共 8 例' in s)
    n2 = render(OUT / 'console_check.txt', FIG / 'console_check.svg',
                '实验七验收：实际终端输出摘录',
                lambda s: s.startswith('PASS') or '项通过' in s)
    print(f'生成 console_tests.svg（{n1} 行）、console_check.svg（{n2} 行）')
