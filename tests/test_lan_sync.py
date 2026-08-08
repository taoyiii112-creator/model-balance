"""局域网同步服务测试。运行：python tests/test_lan_sync.py"""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from modelbalance import lan_sync  # noqa: E402


def _request(port: int, auth: str | None = None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/codex-usage",
        headers={"Authorization": auth} if auth else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class TestLanSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 用固定测试令牌替换真实令牌读取
        cls._orig_token = lan_sync.get_sync_token
        lan_sync.get_sync_token = lambda: "test-token-123"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), lan_sync.LanSyncHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        lan_sync.get_sync_token = cls._orig_token

    def test_unauthorized(self):
        status, _ = _request(self.port)
        self.assertEqual(status, 401)
        status2, _ = _request(self.port, "Bearer wrong-key")
        self.assertEqual(status2, 401)

    def test_authorized_returns_json(self):
        status, data = _request(self.port, "Bearer test-token-123")
        self.assertEqual(status, 200)
        self.assertEqual(data["source"], "codex")
        self.assertIn("records", data)


if __name__ == "__main__":
    unittest.main()
