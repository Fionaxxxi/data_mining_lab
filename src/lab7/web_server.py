"""Local-only web entry point for the lab 7 Agent."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import os
import re
import secrets
import sys
import threading
import webbrowser
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/lab7'))
from agent import ReActAgent
from llm import LLMClient

ENV_FILE = ROOT / '.env'
CSRF_TOKEN = secrets.token_urlsafe(32)
SETTINGS_LOCK = threading.Lock()


def saved_settings():
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding='utf-8-sig').splitlines():
            key, sep, value = line.partition('=')
            if sep and key.strip() in {'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL', 'LAB7_WEB_MODE', 'LLM_TIMEOUT'}:
                values[key.strip()] = value.strip().strip('"\'')
    return values


def public_settings():
    values = saved_settings()
    return {'mode': values.get('LAB7_WEB_MODE', 'offline'),
            'has_key': bool(values.get('OPENAI_API_KEY')),
            'base_url': values.get('OPENAI_BASE_URL', ''),
            'model': values.get('OPENAI_MODEL', ''), 'csrf_token': CSRF_TOKEN}


def save_settings(body):
    mode = body.get('mode')
    if mode not in ('offline', 'model'):
        raise ValueError('请选择离线规则或模型模式')
    base = str(body.get('base_url', '')).strip().rstrip('/')
    model = str(body.get('model', '')).strip()
    key = str(body.get('api_key', '')).strip()
    if len(key) > 500 or any(c in key for c in '\r\n'):
        raise ValueError('API Key 格式不正确')
    if base:
        parsed = urlsplit(base)
        local_http = parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}
        if (len(base) > 300 or parsed.scheme not in {'https', 'http'} or
            (parsed.scheme == 'http' and not local_http) or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            not re.fullmatch(r'/[A-Za-z0-9._/-]*', parsed.path)):
            raise ValueError('Base URL 需为 HTTPS 地址，或本机 HTTP 模型服务')
    if model and not re.fullmatch(r'[A-Za-z0-9._:/-]{1,120}', model):
        raise ValueError('Model Name 格式不正确')
    with SETTINGS_LOCK:
        existing = saved_settings()
        if not key and not body.get('clear_key'):
            key = existing.get('OPENAI_API_KEY', '')
        if mode == 'model' and (not key or not base or not model):
            raise ValueError('模型模式需要 API Key、Base URL 和 Model Name')
        values = {'LAB7_WEB_MODE': mode, 'OPENAI_API_KEY': key,
                  'OPENAI_BASE_URL': base, 'OPENAI_MODEL': model,
                  'LLM_TIMEOUT': existing.get('LLM_TIMEOUT', '60')}
        untouched = []
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text(encoding='utf-8-sig').splitlines():
                if line.partition('=')[0].strip() not in values:
                    untouched.append(line)
        temp = ENV_FILE.with_suffix('.env.tmp')
        temp.write_text(('\n'.join(untouched) + '\n' if untouched else '') +
                        ''.join(f'{name}={value}\n' for name, value in values.items()), encoding='utf-8')
        os.replace(temp, ENV_FILE)
        for name, value in values.items():
            os.environ[name] = value
    return public_settings()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            page = (ROOT / 'web/index.html').read_text(encoding='utf-8')
            graph = json.loads((ROOT / 'outputs/lab6/graph.json').read_text(encoding='utf-8'))
            graph_json = json.dumps(graph, ensure_ascii=False).replace('<', '\\u003c')
            page = re.sub(r'(<script type="application/json" id="graph-data">).*?(</script>)',
                          lambda match: match.group(1) + graph_json + match.group(2), page,
                          count=1, flags=re.DOTALL)
            data = page.replace('</body>', '<script src="/app.js"></script></body>').encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/app.js':
            data = (ROOT / 'web/app.js').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/api/status':
            self.json_response(200, {'mode': public_settings()['mode']})
        elif self.path == '/api/settings':
            self.json_response(200, public_settings())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path not in ('/api/plan', '/api/settings'):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 8192:
                raise ValueError('请求长度不合适')
            body = json.loads(self.rfile.read(size))
            if self.path == '/api/settings':
                expected_origin = 'http://127.0.0.1:%d' % self.server.server_port
                if (self.headers.get('X-CSRF-Token') != CSRF_TOKEN or
                    self.headers.get('Host') != expected_origin.removeprefix('http://') or
                    self.headers.get('Origin') != expected_origin or
                    self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                    self.json_response(403, {'error': '设置请求来源不受信任'})
                    return
                self.json_response(200, save_settings(body))
                return
            query = str(body.get('query', '')).strip()
            if not query or len(query) > 500:
                raise ValueError('请填写 1 至 500 字的需求')
            result = ReActAgent(llm=LLMClient(force_offline=public_settings()['mode'] != 'model')).run(query)
            self.json_response(200, result)
        except (ValueError, json.JSONDecodeError) as exc:
            self.json_response(400, {'error': str(exc)})
        except Exception:
            self.json_response(500, {'error': '规划暂不可用，请检查服务端日志'})

    def json_response(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 8767), Handler)
    print('http://127.0.0.1:8767', flush=True)
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:8767/')).start()
    server.serve_forever()
