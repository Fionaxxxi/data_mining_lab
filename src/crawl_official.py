"""Collect three fixed official route pages and preserve verifiable source evidence.

Usage: python src/crawl_official.py [--offline]
No login, search-result scraping, or website traversal is performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/source'
RAW = ROOT / 'data/raw'
TARGETS = [
    dict(doc_id='HS-O01', scenic='黄山', source_name='黄山旅游官方平台',
         url='https://wap.huangshan.com.cn/detail/strategy/fjqlyzx',
         snapshot='official_huangshan.html', record_id='fjqlyzx-Q20',
         title='黄山风景区清明假期常见旅游咨询 第20问路线节选',
         note='历史清明咨询路线，仅作文本挖掘材料，非2026年开放与票务承诺'),
    dict(doc_id='JZG-O01', scenic='九寨沟', source_name='九寨沟风景名胜区管理局',
         url='https://www.jiuzhai.com/intelligent-service/way-of-play',
         snapshot='official_jiuzhai.html', record_id='way-of-play-one-day',
         title='游玩方式 一日精华游节选',
         note='保留原文时间，包括末段17:00起点早于前段终点的疑似时间重叠，不擅自修订'),
    dict(doc_id='ZJJ-O01', scenic='张家界', source_name='湖南省文化和旅游厅',
         url='https://whhlyt.hunan.gov.cn/whhlyt/wldhlylx/202208/t20220816_27584140.html',
         mirrors=[dict(url='https://www.wlynews.cn/content/2021/09/18/10178438.html',
                       source_name='武陵源区委旅游工作委员会办公室（武陵源新闻网）',
                       record_id='10178438-one-day',
                       note='官方机构署名路线，发布于2021-09-18；作为历史文本挖掘材料，不视为2026年路线更新')],
         snapshot='official_zhangjiajie.html', record_id='t20220816_27584140-one-day',
         title='直达武陵源 乐享张家界 武陵源自驾一日游节选',
         note='网页发布日期2022-08-16，文末署名日期2021-09-18；不视为2026年路线更新'),
]


def extract_route(target: dict, payload: bytes) -> str:
    soup = BeautifulSoup(payload, 'html.parser')
    if target['doc_id'] == 'HS-O01':
        script = soup.find('script', string=lambda s: s and 'var data=' in s)
        match = re.search(r'var data=(\[.*?\]);', script.string, re.S) if script else None
        if not match:
            raise ValueError('黄山页面未找到正文JSON字段')
        data = json.loads(match.group(1))
        ps = BeautifulSoup(data[0]['data']['content'], 'html.parser').find_all('p')
        start = next(i for i, p in enumerate(ps) if '20.清明假期' in p.get_text())
        end = next(i for i, p in enumerate(ps[start + 1:], start + 1)
                   if '21.黄山' in p.get_text())
        route = '\n'.join(str(p) for p in ps[start:end])
        expected = ['云谷', '迎客松', '一日游']
    elif target['doc_id'] == 'JZG-O01':
        heading = soup.find(string=lambda s: s and s.strip() == '一日精华游')
        container = heading.find_parent('div', class_='g-content') if heading else None
        if container is None:
            raise ValueError('九寨沟页面未找到一日精华游正文块')
        route = str(container)
        expected = ['沟口乘车', '13:30', '五彩池']
    else:
        for node in soup(['script', 'style']):
            node.decompose()
        content = soup.select_one('.TRS_Editor') or soup.select_one('#zoom') or soup
        text = content.get_text('\n', strip=True)
        start = text.find('一、武陵源景区自驾一日游')
        end = text.find('二、武陵源外围景区自驾一日游', start + 1)
        if start < 0 or end < 0:
            raise ValueError('张家界页面未找到一日游章节边界')
        route = target['title'] + '\n' + text[start:end].strip()
        expected = ['天子山', '袁家界', '黄石寨']
    if len(route) < 100 or not all(s in route for s in expected):
        raise ValueError('正文长度或路线关键词校验失败')
    return route


def fetch(target: dict) -> tuple[bytes, dict]:
    attempts = []
    sources = [dict(url=target['url'], source_name=target['source_name'],
                    record_id=target['record_id'], note=target['note'])] + target.get('mirrors', [])
    for source in sources:
        for number in range(1, 3):
            started = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
            try:
                request = Request(source['url'], headers={
                    'User-Agent': 'DataMiningCourseLab/1.0 (educational route text collection)',
                    'Accept': 'text/html,application/xhtml+xml',
                })
                with urlopen(request, timeout=25) as response:
                    status = response.status
                    payload = response.read(5 * 1024 * 1024 + 1)
                    final_url = response.url
                    content_type = response.headers.get('Content-Type', '')
                if status != 200 or len(payload) > 5 * 1024 * 1024:
                    raise ValueError('HTTP状态或页面大小异常')
                extract_route(target, payload)
                attempts.append(dict(attempt=number, request_url=source['url'], started_at=started,
                                     http_status=status, result='success'))
                return payload, dict(status='downloaded', final_url=final_url,
                                     source_name=source['source_name'], record_id=source['record_id'],
                                     scope_note=source['note'], content_type=content_type, attempts=attempts,
                                     bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            except Exception as exc:
                attempts.append(dict(attempt=number, request_url=source['url'], started_at=started,
                                     result='failed', error=f'{type(exc).__name__}: {exc}'))
                if number < 2:
                    time.sleep(1)
        time.sleep(1)
    return b'', dict(status='failed', attempts=attempts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='仅解析已保存快照，不发起网络请求')
    args = parser.parse_args()
    SOURCE.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    previous_path = SOURCE / 'crawl_manifest.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    previous_by_id = {item['doc_id']: item for item in previous.get('requests', [])}
    records, logs = [], []
    for target in TARGETS:
        snapshot = SOURCE / target['snapshot']
        payload, log = (b'', dict(status='offline')) if args.offline else fetch(target)
        log.update(doc_id=target['doc_id'], source_url=target['url'])
        if payload:
            snapshot.write_bytes(payload)
            route = extract_route(target, payload)
            provenance = '官方发布页面定向爬取；已保存HTTP采集记录及HTML快照'
            source_file = target['snapshot']
        elif snapshot.exists():
            saved_payload = snapshot.read_bytes()
            route = extract_route(target, saved_payload)
            provenance = '解析已保存官网HTML快照；本次未成功发起或完成下载'
            source_file = target['snapshot']
            log['fallback'] = 'saved_html_snapshot'
            saved = previous_by_id.get(target['doc_id'], {})
            if saved.get('sha256') == hashlib.sha256(saved_payload).hexdigest():
                for key in ('final_url', 'source_name', 'record_id', 'scope_note'):
                    if key in saved:
                        log[key] = saved[key]
                log['sha256'] = saved['sha256']
                log['bytes'] = len(saved_payload)
        elif target['doc_id'] == 'ZJJ-O01':
            source_file = 'official_zhangjiajie_excerpt.txt'
            route = (RAW / source_file).read_text(encoding='utf-8')
            provenance = '官方页面阅读核验；人工摘录，未取得HTML快照'
            log['fallback'] = 'manual_excerpt'
        else:
            raise RuntimeError(f"{target['scenic']}无可用的官方材料，详见请求错误：{log}")
        log['used_source_file'] = source_file
        log['extracted_chars'] = len(route)
        log['extracted_sha256'] = hashlib.sha256(route.encode('utf-8')).hexdigest()
        records.append(dict(
            doc_id=target['doc_id'], scenic=target['scenic'], text_type='官方路线',
            source_name=log.get('source_name', target['source_name']),
            source_url=log.get('final_url', target['url']), original_url=log.get('final_url', target['url']),
            original_text=route, acquired_date=now.date().isoformat(),
            source_record_id=log.get('record_id', target['record_id']), source_file=source_file,
            source_row_index=None, title=target['title'], quality_score=None,
            provenance_status=provenance,
            classification_basis='官方发布机构的路线推荐；一份指南可含多条备选路线',
            scope_note=log.get('scope_note', target['note']),
        ))
        logs.append(log)
        print(f"{target['scenic']}: {log['status']}; source={source_file}; chars={len(route)}", flush=True)
        if not args.offline:
            time.sleep(1)
    (RAW / 'official_routes.jsonl').write_text(
        ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
    manifest = dict(started_at=now.isoformat(timespec='seconds'), mode='offline' if args.offline else 'online',
                    tool='Python urllib.request + BeautifulSoup', timeout_seconds=25,
                    max_attempts_per_url=2, requests=logs,
                    downloaded_pages=sum(x['status'] == 'downloaded' for x in logs),
                    official_documents=len(records))
    name = 'crawl_manifest_offline.json' if args.offline else 'crawl_manifest.json'
    (SOURCE / name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
