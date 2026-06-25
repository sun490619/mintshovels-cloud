#!/usr/bin/env python3
"""需求雷达看板服务器 - 轻量级 HTTP 服务"""
import http.server
import json
import os
import urllib.parse

PORT = 8765
DIR = os.path.dirname(os.path.abspath(__file__))


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_POST(self):
        if self.path == '/api/review':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            action = data.get('action', '')
            name = data.get('name', '')

            # 记录审核操作
            log_file = os.path.join(DIR, 'review_log.jsonl')
            with open(log_file, 'a') as f:
                f.write(json.dumps({
                    'action': action,
                    'name': name,
                    'timestamp': __import__('datetime').datetime.now().isoformat()
                }, ensure_ascii=False) + '\n')

            print(f"📋 审核: {action.upper()} — {name}")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True}).encode())
        elif self.path == '/api/run-tests':
            # 触发测试
            import subprocess
            print("🧪 收到重新测试请求...")
            try:
                result = subprocess.run(
                    ['node', 'test_tools.mjs'],
                    cwd=DIR,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                print(result.stdout[-500:] if result.stdout else '')
                if result.stderr:
                    print("STDERR:", result.stderr[:500])
            except Exception as e:
                print(f"⚠️ 测试出错: {e}")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # 静默日志


if __name__ == '__main__':
    print(f"\n🔭 需求雷达看板已启动")
    print(f"   👉 打开浏览器访问: http://localhost:{PORT}/demand_dashboard.html")
    print(f"   📋 审核记录: {DIR}/review_log.jsonl")
    print(f"   ⏎ 按 Ctrl+C 停止\n")
    server = http.server.HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n👋 看板已停止')
        server.shutdown()
