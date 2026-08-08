"""消息中心存储测试：增删查、去重、已读、清理。运行：python tests/test_notifications.py"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestNotifications(unittest.TestCase):
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

    def test_add_and_list(self):
        import modelbalance.storage as storage

        storage.init_db()
        nid = storage.add_notification(
            "low_balance",
            "低余额提醒",
            "deepseek-main 可用余额低于阈值。",
            dedupe_key="low_balance:deepseek-main:2026-08-09",
        )
        self.assertIsInstance(nid, int)
        items = storage.list_notifications()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "低余额提醒")
        self.assertEqual(items[0]["type"], "low_balance")
        self.assertEqual(items[0]["read"], 0)
        self.assertEqual(storage.unread_notification_count(), 1)

    def test_dedupe_key_ignored(self):
        import modelbalance.storage as storage

        storage.init_db()
        storage.add_notification("low_balance", "t", "b", dedupe_key="k1")
        nid2 = storage.add_notification("low_balance", "t", "b", dedupe_key="k1")
        self.assertEqual(nid2, 0)
        self.assertEqual(len(storage.list_notifications()), 1)
        storage.add_notification("info", "t2", "b2", dedupe_key="k2")
        storage.add_notification("info", "t3", "b3", dedupe_key=None)
        self.assertEqual(len(storage.list_notifications()), 3)

    def test_mark_read_and_delete(self):
        import modelbalance.storage as storage

        storage.init_db()
        nid = storage.add_notification(
            "update_available", "发现新版本 v0.3.0", "更新内容"
        )
        self.assertEqual(storage.mark_notification_read(nid), 1)
        self.assertEqual(storage.unread_notification_count(), 0)
        self.assertEqual(storage.mark_notification_read(999999), 0)
        self.assertEqual(storage.delete_notification(nid), 1)
        self.assertEqual(storage.list_notifications(), [])

    def test_mark_all_read(self):
        import modelbalance.storage as storage

        storage.init_db()
        storage.add_notification("low_balance", "t1", "b1", dedupe_key="a")
        storage.add_notification("low_balance", "t2", "b2", dedupe_key="b")
        self.assertEqual(storage.mark_all_notifications_read(), 2)
        self.assertEqual(storage.unread_notification_count(), 0)
        self.assertEqual(storage.mark_all_notifications_read(), 0)

    def test_prune_old(self):
        import modelbalance.storage as storage

        storage.init_db()
        old = (datetime.now() - timedelta(days=100)).isoformat(timespec="seconds")
        with storage._db() as conn:
            conn.execute(
                "INSERT INTO notifications (type, title, body, read, created_at) "
                "VALUES (?,?,?,0,?)",
                ("low_balance", "old", "old", old),
            )
        deleted = storage.prune_notifications(keep_days=90)
        self.assertEqual(deleted, 1)
        storage.add_notification("low_balance", "new", "new", dedupe_key="n")
        items = storage.list_notifications()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "new")

    def test_init_db_creates_table(self):
        import sqlite3

        import modelbalance.storage as storage

        storage.init_db()
        with storage._db() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("notifications", tables)


if __name__ == "__main__":
    unittest.main()
