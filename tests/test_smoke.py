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

if __name__ == "__main__":
    unittest.main()