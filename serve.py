#!/usr/bin/env python3
"""mermaidfix 工作台: 静态文件 + POST /save 写回 .mmd + POST /chat 解惑代理(SSE 透传)
用法: python3 serve.py [端口=8642]
"""
import http.server, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

CHAT_SYSTEM = '''你是 mermaid 流程图的解惑助手。用户画板上当前这张图的源码:

```mermaid
{code}
```

规则:
1. 只回答问题:解释流程含义、节点与连线关系、mermaid 语法、业务逻辑疑点、给思路建议。简洁中文,直接答重点。
2. 你没有任何修改能力,不要输出整段改好的代码;用户要改图时提醒他:直接改左侧代码(实时重渲),或把需求交给终端 `mermaid` 命令重新生成。
3. 图里没有的信息,可基于常识回答,但注明是推测。'''

FIX_SYSTEM = '''你是 mermaid 渲染错误修复器。用户给你一段渲染时报错的 mermaid 代码和报错信息。
只做最小修改修复错误:保持节点、连线、文字、配色语义完全不变。
常见错因:linkStyle 索引超出实际边数(边从 0 计数,索引必须小于边总数)、class/style 引用了不存在的节点 ID、label 字符串没用双引号包裹、frontmatter YAML 缩进错误。
只输出修好的完整 mermaid 代码:不要解释、不要 markdown 围栏。'''

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        if self.path != '/list':
            return super().do_GET()
        files = sorted((f for f in os.listdir(ROOT) if f.endswith('.mmd')),
                       key=lambda f: os.path.getmtime(os.path.join(ROOT, f)), reverse=True)
        body = json.dumps(files).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == '/chat':
            return self._chat()
        if self.path == '/fix':
            return self._fix()
        if self.path != '/save':
            self.send_error(404); return
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        name = os.path.basename(body['file'])  # 防路径穿越
        if not name.endswith('.mmd'):
            self.send_error(400, 'only .mmd files'); return
        with open(os.path.join(ROOT, name), 'w', encoding='utf-8') as f:
            f.write(body['code'])
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')

    def _fix(self):
        """渲染错误回炉:坏代码 + 报错 → AI 最小修复 → 返回修好的代码(非流式)"""
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with open(os.path.join(ROOT, 'config.json')) as f:
            cfg = json.load(f)
        payload = {
            'model': cfg['model'],
            'messages': [
                {'role': 'system', 'content': FIX_SYSTEM},
                {'role': 'user', 'content': f"渲染报错: {body.get('error', '')}\n\n代码:\n{body.get('code', '')}"},
            ],
            'max_tokens': 8000,
            'enable_thinking': False,
        }
        req = urllib.request.Request(
            cfg['endpoint'].rstrip('/') + '/v1/chat/completions',
            data=json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + cfg['key'],
                     'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            out = data['choices'][0]['message']['content'].strip()
            import re
            m = re.search(r'```(?:mermaid)?\s*\n(.*?)```', out, re.DOTALL)
            resp = json.dumps({'code': (m.group(1).strip() if m else out)}).encode()
            self.send_response(200)
        except Exception as e:
            resp = json.dumps({'error': str(e)[:200]}).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def _chat(self):
        """解惑代理:组 system(嵌当前图代码) → 转发上游 stream → SSE 逐行透传。
        浏览器不直连网关(CORS),API key 只留在服务端。"""
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with open(os.path.join(ROOT, 'config.json')) as f:
            cfg = json.load(f)
        payload = {
            'model': cfg['model'],
            'messages': [{'role': 'system',
                          'content': CHAT_SYSTEM.format(code=body.get('code', ''))},
                         *body.get('messages', [])],
            'stream': True,
            'max_tokens': 2000,
            'enable_thinking': bool(body.get('thinking')),
        }
        req = urllib.request.Request(
            cfg['endpoint'].rstrip('/') + '/v1/chat/completions',
            data=json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + cfg['key'],
                     'Content-Type': 'application/json'})
        try:
            upstream = urllib.request.urlopen(req, timeout=180)
        except Exception as e:
            detail = getattr(e, 'read', lambda: b'')()[:200].decode('utf-8', 'replace') or str(e)
            err = json.dumps({'error': detail}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(err)))
            self.end_headers()
            self.wfile.write(err)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        try:
            with upstream:
                for line in upstream:
                    self.wfile.write(line)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # 用户关了抽屉/页面,静默

    def log_message(self, *a): pass

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8642
    print(f'mermaidfix: http://localhost:{port}/preview.html')
    http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
