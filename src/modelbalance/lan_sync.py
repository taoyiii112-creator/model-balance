"""局域网同步服务：向手机端提供 Codex 用量 JSON（只读接口，Bearer 鉴权）。

运行：python run.py lan-sync（默认 0.0.0.0:8002）
手机端访问：http://<电脑局域网IP>:8002/api/codex-usage
鉴权：Authorization: Bearer <config.json 中任一账户的 API Key>
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .codex_usage import export_json, scan_codex_sessions
from .config import load_accounts


class LanSyncHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 静默访问日志
        pass

    def _send_json(self, obj, status: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        auth = self.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip() if auth else ""
        if not token:
            return False
        accounts = load_accounts()
        return any(token == acc.api_key for acc in accounts if acc.api_key)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/__mb_health":
            self._send_json({"service": "modelbalance-lan-sync", "ok": True})
            return
        if path != "/api/codex-usage":
            self._send_json({"error": "not found"}, 404)
            return
        if not self._authorized():
            self._send_json({"error": "unauthorized"}, 401)
            return
        try:
            records = scan_codex_sessions()
            self._send_json(export_json(records))
        except Exception as exc:  # noqa: BLE001 - 服务端兜底
            self._send_json({"error": f"提取失败: {exc}"}, 500)


def run_lan_sync(host: str = "0.0.0.0", port: int = 8002) -> int:
    server = ThreadingHTTPServer((host, port), LanSyncHandler)
    print(f"局域网同步服务已启动: http://{host}:{port}")
    print("手机端填写电脑局域网 IP（如 192.168.x.x），端口 8002")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()
    return 0
