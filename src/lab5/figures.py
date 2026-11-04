"""Render traveler comparison; report samples and counts use Markdown tables."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "outputs" / "lab5"
FIG = OUT / "figures"
FIG.mkdir(exist_ok=True)
stats = json.loads((OUT / "stats.json").read_text(encoding="utf8"))

labels = ['��ͨ�ο�', '����Լ���ο�', '���γ��ο�', '�����ο�', '�����ο�']
counts = [stats['by_traveler'].get(label, 0) for label in labels]
width, height = 920, 430
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<rect width="100%" height="100%" fill="white"/>',
         '<text x="30" y="43" font-size="24" font-family="Microsoft YaHei,sans-serif" font-weight="bold">���ο�����ͳ������������ӳ��</text>']
for i, (label, count) in enumerate(zip(labels, counts)):
    y = 92 + i * 61
    parts.append(f'<text x="30" y="{y+16}" font-size="18" font-family="Microsoft YaHei,sans-serif">{label}</text>')
    parts.append(f'<rect x="210" y="{y-4}" width="600" height="26" fill="#eef2f6"/>')
    if count:
        parts.append(f'<rect x="210" y="{y-4}" width="{600*count/max(counts):.1f}" height="26" fill="#337ab7"/>')
    parts.append(f'<text x="825" y="{y+16}" font-size="18" font-family="Microsoft YaHei,sans-serif">{count}</text>')
parts.append('<text x="30" y="412" font-size="15" fill="#555" font-family="Microsoft YaHei,sans-serif">��λ��ȥ�غ��ӳ��������0 ��ʾ������û�пɺ����¼</text></svg>')
(FIG / 'traveler_bar.svg').write_text(''.join(parts), encoding='utf8')
