"""离线冒烟测试：不访问网络。运行：python tests/test_smoke.py"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from modelbalance.models import UsageRecord  # noqa: E402
from modelbalance.providers.deepseek import _to_float, parse_balance as parse_deepseek  # noqa: E402
from modelbalance.providers.openai_compat import parse_balance as parse_relay  # noqa: E402


class TestModels(unittest.TestCase):
    def test_usage_record_tokens(self):
        rec = UsageRecord(account="a", model="m", prompt_tokens=10, completion_tokens=5)
        self.assertEqual(rec.total_tokens, 15)

    def test_to_float(self):
        self.assertEqual(_to_float("110.00"), 110.0)
        self.assertIsNone(_to_float("abc"))
        self.assertIsNone(_to_float(None))


class TestDeepSeekParse(unittest.TestCase):
    def test_parse(self):
        data = {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "110.00",
                    "granted_balance": "10.00",
                    "topped_up_balance": "100.00",
                }
            ],
        }
        b = parse_deepseek("ds-main", data)
        self.assertAlmostEqual(b.available, 110.0)
        self.assertAlmostEqual(b.granted, 10.0)
        self.assertAlmostEqual(b.topped_up, 100.0)
        self.assertEqual(b.currency, "CNY")

    def test_unavailable(self):
        from modelbalance.providers.base import ProviderError

        with self.assertRaises(ProviderError):
            parse_deepseek("ds-main", {"is_available": False})


class TestRelayParse(unittest.TestCase):
    def test_parse(self):
        payload = {"data": {"quota": 500000, "used_quota": 100000}}
        b = parse_relay("relay-1", payload, 500000, "CNY")
        self.assertAlmostEqual(b.available, 1.0)
        self.assertAlmostEqual(b.used, 0.2)


class TestStorage(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage

        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name)
        storage.DB_PATH = storage.DATA_DIR / "test.db"

    def tearDown(self):
        import modelbalance.storage as storage

        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_usage_roundtrip(self):
        import modelbalance.storage as storage

        storage.init_db()
        rid = storage.add_usage_record(
            UsageRecord(account="ds-main", model="deepseek-chat", prompt_tokens=100, completion_tokens=50, cost=0.12)
        )
        self.assertIsInstance(rid, int)
        records = storage.list_usage_records("ds-main")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["total_tokens"], 150)
        totals = storage.usage_totals("ds-main")
        self.assertEqual(totals["total_tokens"], 150)
        self.assertAlmostEqual(totals["cost"], 0.12)


class TestOpenAIParse(unittest.TestCase):
    def test_parse(self):
        from modelbalance.providers.openai import parse_balance

        b = parse_balance("oa-1", {"total_granted": 100.0, "total_used": 30.0, "total_available": 70.0})
        self.assertAlmostEqual(b.available, 70.0)
        self.assertAlmostEqual(b.used, 30.0)
        self.assertAlmostEqual(b.total, 100.0)
        self.assertEqual(b.currency, "USD")

    def test_bad_payload(self):
        from modelbalance.providers.base import ProviderError
        from modelbalance.providers.openai import parse_balance

        with self.assertRaises(ProviderError):
            parse_balance("oa-1", {"foo": 1})

class TestUsageStats(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage

        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name)
        storage.DB_PATH = storage.DATA_DIR / "test.db"

    def tearDown(self):
        import modelbalance.storage as storage

        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_cache_breakdown(self):
        import modelbalance.storage as storage
        from datetime import datetime

        storage.init_db()
        storage.add_usage_record(
            UsageRecord(
                account="cache-test", model="deepseek-chat",
                prompt_tokens=300, completion_tokens=50,
                prompt_cache_hit_tokens=200, prompt_cache_miss_tokens=100,
                cost=0.5,
            )
        )
        bd = storage.usage_breakdown(account="cache-test")
        self.assertEqual(bd["cache_hit"], 200)
        self.assertEqual(bd["cache_miss"], 100)
        self.assertEqual(bd["output"], 50)

    def test_daily_aggregation(self):
        import modelbalance.storage as storage
        from datetime import datetime

        storage.init_db()
        storage.add_usage_record(
            UsageRecord(account="daily-test", model="m", prompt_tokens=100, completion_tokens=50, cost=0.12)
        )
        daily = storage.usage_daily(account="daily-test", days=7)
        self.assertEqual(len(daily), 7)
        last = daily[-1]
        self.assertEqual(last["day"], datetime.now().strftime("%Y-%m-%d"))
        self.assertGreaterEqual(last["tokens"], 150)
        self.assertGreaterEqual(last["cost"], 0.12)

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request as urlrequest

from modelbalance.config import Account


class TestUsageParse(unittest.TestCase):
    def test_deepseek_style(self):
        from modelbalance.proxy import extract_usage

        u = extract_usage(
            {"usage": {"prompt_tokens": 300, "completion_tokens": 50, "prompt_cache_hit_tokens": 200, "prompt_cache_miss_tokens": 100}}
        )
        self.assertEqual(u, {"prompt": 300, "completion": 50, "hit": 200, "miss": 100})

    def test_openai_style(self):
        from modelbalance.proxy import extract_usage

        u = extract_usage(
            {"usage": {"prompt_tokens": 300, "completion_tokens": 50, "prompt_tokens_details": {"cached_tokens": 120}}}
        )
        self.assertEqual(u["hit"], 120)
        self.assertEqual(u["miss"], 180)

    def test_estimate_cost(self):
        from modelbalance.proxy import estimate_cost

        usage = {"prompt": 300, "completion": 50, "hit": 200, "miss": 100}
        cost = estimate_cost({"input": 2.0, "input_cache_hit": 0.5, "output": 8.0}, usage)
        self.assertAlmostEqual(cost, (100 * 2.0 + 200 * 0.5 + 50 * 8.0) / 1_000_000, places=8)
        self.assertIsNone(estimate_cost(None, usage))


class FakeUpstream(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        body = json.dumps(
            {
                "id": "fake-1",
                "object": "chat.completion",
                "model": "deepseek-chat",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 300,
                    "completion_tokens": 50,
                    "total_tokens": 350,
                    "prompt_cache_hit_tokens": 200,
                    "prompt_cache_miss_tokens": 100,
                },
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


class TestProxyIntegration(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage
        from modelbalance.proxy import ProxyHandler

        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name)
        storage.DB_PATH = storage.DATA_DIR / "test.db"

        os.environ["TEST_API_KEY"] = "sk-test"
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeUpstream)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()

        ProxyHandler.accounts = [
            Account(
                name="relay-test",
                provider="openai_compat",
                api_key_env="TEST_API_KEY",
                base_url=f"http://127.0.0.1:{self.upstream.server_port}",
            )
        ]
        self.proxy = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
        threading.Thread(target=self.proxy.serve_forever, daemon=True).start()

    def tearDown(self):
        import modelbalance.storage as storage

        self.proxy.shutdown()
        self.upstream.shutdown()
        self.proxy.server_close()
        self.upstream.server_close()
        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_proxy_records_usage(self):
        import modelbalance.storage as storage

        req = urlrequest.Request(
            f"http://127.0.0.1:{self.proxy.server_port}/v1/chat/completions",
            data=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}).encode("utf-8"),
            headers={"Authorization": "Bearer sk-test", "Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data["model"], "deepseek-chat")
        recs = storage.list_usage_records("relay-test")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["prompt_cache_hit_tokens"], 200)
        self.assertEqual(recs[0]["prompt_cache_miss_tokens"], 100)
        self.assertEqual(recs[0]["completion_tokens"], 50)

    def test_proxy_is_running(self):
        from modelbalance.proxy import proxy_is_running

        self.assertTrue(proxy_is_running(self.proxy.server_port))
        self.assertFalse(proxy_is_running(59999))

class TestUpdater(unittest.TestCase):
    def test_version_compare(self):
        from modelbalance.updater import is_newer, parse_version

        self.assertTrue(is_newer("0.1.0", "0.2.0"))
        self.assertTrue(is_newer("0.2.0", "0.2.1"))
        self.assertFalse(is_newer("0.2.0", "0.2.0"))
        self.assertFalse(is_newer("0.3.0", "0.2.0"))
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))

    def test_fmt_size(self):
        from modelbalance.updater import fmt_size

        self.assertEqual(fmt_size(2 * 1024 * 1024), "2.0 MB")
        self.assertTrue(fmt_size(500 * 1024).endswith("KB"))

    def test_parse_release(self):
        from modelbalance.updater import parse_release

        data = {
            "tag_name": "v0.2.0",
            "body": "新增更新功能",
            "assets": [
                {"name": "model-balance-0.2.0.zip", "size": 2097152, "browser_download_url": "https://example.com/x.zip"},
                {"name": "README.md", "size": 10},
            ],
        }
        info = parse_release(data)
        self.assertEqual(info["tag_name"], "v0.2.0")
        self.assertEqual(info["asset_size"], 2097152)
        self.assertIsNone(parse_release({"tag_name": "v0.2.0", "assets": []}))

    def test_apply_update_preserves_user_data(self):
        import zipfile

        from modelbalance.updater import apply_update

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            app_dir = base / "app"
            app_dir.mkdir()
            (app_dir / ".env").write_text("K=old", encoding="utf-8")
            (app_dir / "data").mkdir()
            (app_dir / "config.json").write_text("{}", encoding="utf-8")
            (app_dir / "old.txt").write_text("old", encoding="utf-8")
            zip_path = base / "pkg.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("new.txt", "new")
                zf.writestr("src/__init__.py", "x")
            apply_update(zip_path, app_dir)
            self.assertEqual((app_dir / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertTrue((app_dir / "src" / "__init__.py").exists())
            self.assertTrue((app_dir / ".env").exists())
            self.assertTrue((app_dir / "config.json").exists())
            self.assertTrue((app_dir / "data").is_dir())

class FakeStreamUpstream(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        chunks = [
            b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"\xe5\xa5\xbd"}}]}\n\n',
            b'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":10,"completion_tokens":4,"prompt_cache_hit_tokens":3,"prompt_cache_miss_tokens":7}}\n\n',
            b'data: [DONE]\n\n',
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(sum(len(c) for c in chunks)))
        self.end_headers()
        for c in chunks:
            self.wfile.write(c)
        self.wfile.flush()

    def log_message(self, fmt, *args):
        pass


class TestProxyStreaming(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage
        from modelbalance.proxy import ProxyHandler

        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name)
        storage.DB_PATH = storage.DATA_DIR / "test.db"
        os.environ["TEST_API_KEY"] = "sk-test"
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeStreamUpstream)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        ProxyHandler.accounts = [
            Account(
                name="stream-test",
                provider="openai_compat",
                api_key_env="TEST_API_KEY",
                base_url=f"http://127.0.0.1:{self.upstream.server_port}",
            )
        ]
        self.proxy = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
        threading.Thread(target=self.proxy.serve_forever, daemon=True).start()

    def tearDown(self):
        import modelbalance.storage as storage

        self.proxy.shutdown()
        self.upstream.shutdown()
        self.proxy.server_close()
        self.upstream.server_close()
        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_stream_forward_and_record(self):
        import modelbalance.storage as storage

        req = urlrequest.Request(
            f"http://127.0.0.1:{self.proxy.server_port}/v1/chat/completions",
            data=json.dumps(
                {"model": "deepseek-chat", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
            ).encode("utf-8"),
            headers={"Authorization": "Bearer sk-test", "Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
        self.assertIn("[DONE]", body)
        recs = storage.list_usage_records("stream-test")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["prompt_cache_hit_tokens"], 3)
        self.assertEqual(recs[0]["prompt_cache_miss_tokens"], 7)
        self.assertEqual(recs[0]["completion_tokens"], 4)


class TestUpdaterMore(unittest.TestCase):
    def test_configurable_source(self):
        import modelbalance.updater as updater

        with tempfile.TemporaryDirectory() as td:
            updater.UPDATE_SOURCE_FILE = Path(td) / "update_source.json"
            updater.set_update_source("https://example.com/updates/latest.json")
            self.assertEqual(updater.get_update_source(), "https://example.com/updates/latest.json")
            updater.set_update_source("")
            self.assertEqual(updater.get_update_source(), updater.RELEASE_API)
        updater.UPDATE_SOURCE_FILE = updater.PROJECT_ROOT / "data" / "update_source.json"

    def test_validate_zip(self):
        import zipfile

        from modelbalance.updater import validate_zip

        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "good.zip"
            with zipfile.ZipFile(good, "w") as zf:
                zf.writestr("a.txt", "hi")
            validate_zip(good)  # 正常不抛异常
            bad = Path(td) / "bad.zip"
            bad.write_bytes(b"not a zip at all")
            with self.assertRaises(Exception):
                validate_zip(bad)

    def test_cleanup_updates(self):
        from modelbalance.updater import cleanup_updates

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.zip").write_bytes(b"x")
            (d / "b.zip").write_bytes(b"y")
            cleanup_updates(d, keep=d / "a.zip")
            self.assertTrue((d / "a.zip").exists())
            self.assertFalse((d / "b.zip").exists())
            cleanup_updates(d)
            self.assertFalse((d / "a.zip").exists())

class TestSnapshots(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage

        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name)
        storage.DB_PATH = storage.DATA_DIR / "test.db"

    def tearDown(self):
        import modelbalance.storage as storage

        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_snapshot_history(self):
        import modelbalance.storage as storage
        from modelbalance.models import Balance

        storage.init_db()
        storage.add_snapshot(Balance(account="ds-main", provider="deepseek", currency="CNY", available=10.0))
        storage.add_snapshot(Balance(account="ds-main", provider="deepseek", currency="CNY", available=9.5))
        hist = storage.snapshot_history(account="ds-main", days=30)
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0]["available"], 10.0)
        self.assertEqual(hist[1]["available"], 9.5)


class TestWeb(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage

        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name)
        storage.DB_PATH = storage.DATA_DIR / "test.db"

        from modelbalance.web import Handler

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        import modelbalance.storage as storage

        self.server.shutdown()
        self.server.server_close()
        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_page_and_usage_api(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        with urlrequest.urlopen(base + "/", timeout=10) as resp:
            page = resp.read().decode("utf-8")
        self.assertIn('id="bal"', page)
        self.assertIn("costChart", page)
        with urlrequest.urlopen(base + "/api/usage", timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("totals", data)
        self.assertIn("daily", data)
        self.assertIn("breakdown", data)


class TestCli(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage

        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name)
        storage.DB_PATH = storage.DATA_DIR / "test.db"

    def tearDown(self):
        import modelbalance.storage as storage

        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_parser_subcommands(self):
        from modelbalance import cli

        parser = cli.build_parser()
        names = set(parser._subparsers._group_actions[0].choices.keys())
        for expected in ("balance", "usage", "add-usage", "watch", "web", "app", "proxy", "init-db", "set-update-source"):
            self.assertIn(expected, names)

    def test_add_usage_command(self):
        import argparse

        import modelbalance.storage as storage
        from modelbalance import cli

        args = argparse.Namespace(
            account="cli-test", model="deepseek-chat", prompt=0,
            cache_hit=10, cache_miss=5, completion=3, cost=0.1, note="x",
        )
        rc = cli.cmd_add_usage(args)
        self.assertEqual(rc, 0)
        totals = storage.usage_totals(account="cli-test")
        self.assertEqual(totals["prompt_cache_hit_tokens"], 10)
        self.assertEqual(totals["prompt_cache_miss_tokens"], 5)
        self.assertEqual(totals["completion_tokens"], 3)
        self.assertEqual(cli.cmd_usage(argparse.Namespace(account="cli-test", since=None)), 0)


class TestProxyHealth(unittest.TestCase):
    def test_health_endpoint(self):
        import modelbalance.storage as storage
        from modelbalance.proxy import ProxyHandler, proxy_is_running

        with tempfile.TemporaryDirectory() as td:
            storage.DATA_DIR = Path(td)
            storage.DB_PATH = storage.DATA_DIR / "test.db"
            ProxyHandler.accounts = []
            srv = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                self.assertTrue(proxy_is_running(srv.server_port))
                with urlrequest.urlopen(f"http://127.0.0.1:{srv.server_port}/__mb_health", timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["service"], "modelbalance-proxy")
                self.assertFalse(proxy_is_running(59998))
            finally:
                srv.shutdown()
                srv.server_close()

class TestConfigSettings(unittest.TestCase):
    def test_load_save_settings(self):
        import json

        from modelbalance.config import DEFAULT_ALERT_THRESHOLD, load_settings, save_setting

        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.json"
            self.assertEqual(load_settings(cfg)["alert_threshold"], DEFAULT_ALERT_THRESHOLD)
            self.assertTrue(save_setting("alert_threshold", 3.5, cfg))
            self.assertEqual(load_settings(cfg)["alert_threshold"], 3.5)
            data = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertAlmostEqual(data["alert_threshold"], 3.5)

    def test_invalid_threshold_falls_back(self):
        from modelbalance.config import DEFAULT_ALERT_THRESHOLD, load_settings

        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.json"
            cfg.write_text('{"alert_threshold": "abc"}', encoding="utf-8")
            self.assertEqual(load_settings(cfg)["alert_threshold"], DEFAULT_ALERT_THRESHOLD)

if __name__ == "__main__":
    unittest.main()