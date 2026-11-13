"""把真实控制台输出渲染为图片，作为运行截图证据。

文本不是手写：测试与验收的 stdout 由子进程实时捕获后原样绘制；
原始文本同时保存在 outputs/lab7/test_run.log 与 console_*.txt。
"""
from pathlib import Path
import subprocess
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'outputs/lab7'
FIG = OUT / 'figures'
FONT = r'C:\Windows\Fonts\msyh.ttc'
SIZE, PAD, LH, WIDTH = 16, 26, 27, 2040


def run(args):
    p = subprocess.run([sys.executable] + args, cwd=str(ROOT), capture_output=True, text=True)
    return p.stdout + (('\n[stderr]\n' + p.stderr) if p.stderr.strip() else '')


def render(lines, path):
    font = ImageFont.truetype(FONT, SIZE)
    wrapped = []
    for ln in lines:
        for sub in str(ln).splitlines() or ['']:
            wrapped += textwrap.wrap(sub, width=112, drop_whitespace=False) or ['']
    h = PAD * 2 + LH * len(wrapped)
    img = Image.new('RGB', (WIDTH, h), (24, 26, 30))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(wrapped):
        color = (120, 220, 160) if ln.startswith('PS ') else (225, 228, 232)
        if ln.startswith('[') and ('通过' in ln or '失败' in ln):
            color = (150, 210, 255)
        if ln.startswith('PASS'):
            color = (140, 225, 165)
        if ln.startswith('FAIL'):
            color = (255, 140, 140)
        d.text((PAD, PAD + i * LH), ln, font=font, fill=color)
    img.save(path)
    print(path.name, img.size, path.stat().st_size)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    t = run(['src/lab7/tests.py'])
    (OUT / 'console_tests.txt').write_text(t, encoding='utf8')
    c = run(['src/lab7/check.py'])
    (OUT / 'console_check.txt').write_text(c, encoding='utf8')
    render(['PS E:\\data_mining_lab\\data_mining_lab-main> $env:PYTHONUTF8=1',
            'PS> python src\\lab7\\cli.py --query "亲子去九寨沟玩一天，想看水"',
            run(['src/lab7/cli.py', '--query', '亲子去九寨沟玩一天，想看水']),
            '',
            'PS> python src\\lab7\\tests.py',
            t], FIG / 'console_tests.png')
    render(['PS> python src\\lab7\\check.py',
            c], FIG / 'console_check.png')


if __name__ == '__main__':
    main()
