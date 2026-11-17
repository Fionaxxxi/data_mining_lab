"""Local HTTP smoke check for the Web entry point."""
import json
import threading
import tempfile
import urllib.request
import web_server
from web_server import Handler, ThreadingHTTPServer

temp_dir = tempfile.TemporaryDirectory()
web_server.ENV_FILE = web_server.Path(temp_dir.name) / '.env'

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = 'http://127.0.0.1:%d' % server.server_port
try:
    html = opener.open(base + '/').read().decode('utf-8')
    start = html.index('id="graph-data"')
    start = html.index('>', start) + 1
    graph = json.loads(html[start:html.index('</script>', start)])
    assert len(graph['nodes']) == 471 and len(graph['edges']) == 629
    assert '/app.js' in html
    assert opener.open(base + '/app.js').status == 200
    status = json.load(opener.open(base + '/api/status'))
    assert status['mode'] == 'offline'
    config = json.load(opener.open(base + '/api/settings'))
    assert not config['has_key'] and 'api_key' not in config
    settings_body = json.dumps({'mode': 'model', 'api_key': 'test-key',
                                'base_url': 'https://example.com/v1', 'model': 'test-model'}).encode()
    settings_req = urllib.request.Request(base + '/api/settings', data=settings_body,
        headers={'Content-Type': 'application/json', 'Origin': base,
                 'X-CSRF-Token': config['csrf_token']})
    saved = json.load(opener.open(settings_req))
    assert saved['mode'] == 'model' and saved['has_key'] and 'api_key' not in saved
    assert 'OPENAI_API_KEY=test-key' in web_server.ENV_FILE.read_text(encoding='utf-8')
    offline_req = urllib.request.Request(base + '/api/settings',
        data=json.dumps({'mode': 'offline', 'base_url': '', 'model': '', 'clear_key': True}).encode(),
        headers={'Content-Type': 'application/json', 'Origin': base,
                 'X-CSRF-Token': config['csrf_token']})
    assert json.load(opener.open(offline_req))['mode'] == 'offline'
    for query, expected in [
        ('带老人去黄山玩一天', '黄山'),
        ('一家三口亲子游九寨沟一天', '九寨沟'),
        ('情侣去张家界玩两天', '张家界'),
        ('推荐一下泰山的路线', None),
        ('帮我做个旅游规划', None),
    ]:
        req = urllib.request.Request(base + '/api/plan',
                                     data=json.dumps({'query': query}, ensure_ascii=False).encode(),
                                     headers={'Content-Type': 'application/json'})
        result = json.load(opener.open(req))
        assert result['plan']['scenic'] == expected, (query, result['plan']['scenic'])
        assert 'traces' in result and 'tool_calls' in result
    print('Web smoke passed: settings save, full graph, assets, 3 scenic routes, unknown and vague requests')
finally:
    server.shutdown()
    temp_dir.cleanup()
