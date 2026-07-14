#!/usr/bin/env python3
"""mermaidfix 工作台: 静态文件 + POST /save 把编辑器内容写回 .mmd
用法: python3 serve.py [端口=8642]
"""
import http.server, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

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
        if self.path != '/save':
            self.send_error(404); return
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        name = os.path.basename(body['file'])  # 防路径穿越
        if not name.endswith('.mmd'):
            self.send_error(400, 'only .mmd files'); return
        with open(os.path.join(ROOT, name), 'w', encoding='utf-8') as f:
            f.write(body['code'])
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')

    def log_message(self, *a): pass

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8642
    print(f'mermaidfix: http://localhost:{port}/preview.html')
    http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
