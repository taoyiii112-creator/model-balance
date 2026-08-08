"""Codex 会话用量提取解析测试。运行：python tests/test_codex_usage.py"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from modelbalance.codex_usage import (  # noqa: E402
    export_json,
    parse_session_file,
    scan_codex_sessions,
    sync_codex_usage_to_db,
)


SAMPLE = """\
{"timestamp":"2026-08-02T04:51:19.535Z","type":"session_meta","payload":{"session_id":"s1","id":"s1","timestamp":"2026-08-02T04:51:19Z","cwd":"C:\\\\work\\\\my-project","originator":"codex_work_desktop","model_provider":"deepseek"}}
{"timestamp":"2026-08-02T04:51:19.535Z","type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":13167,"cached_input_tokens":0,"output_tokens":119,"total_tokens":13286},"last_token_usage":{"input_tokens":13167,"cached_input_tokens":0,"output_tokens":119,"total_tokens":13286}}}}
{"timestamp":"2026-08-02T04:55:23.046Z","type":"event_msg","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":1000,"cached_input_tokens":600,"output_tokens":50,"total_tokens":1050}}}}
"""


def _write_session(codex_dir: Path) -> Path:
    p = codex_dir / "sessions" / "2026" / "08" / "02"
    p.mkdir(parents=True, exist_ok=True)
    f = p / "rollout-test.jsonl"
    f.write_text(SAMPLE, encoding="utf-8")
    return f


class TestParseSessionFile(unittest.TestCase):
    def test_parse_fields_and_cache_split(self):
        with tempfile.TemporaryDirectory() as td:
            f = _write_session(Path(td))
            session_id, cwd, records = parse_session_file(f)
            self.assertEqual(session_id, "s1")
            self.assertEqual(cwd, r"C:\work\my-project")
            self.assertEqual(len(records), 2)

            first, second = records
            self.assertEqual(first.input_tokens, 13167)
            self.assertEqual(first.cached_input_tokens, 0)
            self.assertEqual(first.cache_miss_tokens, 13167)
            self.assertEqual(first.output_tokens, 119)
            self.assertEqual(first.total_tokens, 13286)

            self.assertEqual(second.cached_input_tokens, 600)
            self.assertEqual(second.cache_miss_tokens, 400)
            self.assertEqual(second.output_tokens, 50)
            self.assertEqual(second.total_tokens, 1050)


    def test_cumulative_total_delta(self):
        """total_token_usage 为会话累计值时，按增量统计。"""
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "sessions" / "s.jsonl"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(
                '{"timestamp":"2026-08-02T04:51:19Z","type":"event_msg","payload":'
                '{"type":"token_count","info":{"total_token_usage":{"input_tokens":13167,'
                '"cached_input_tokens":0,"output_tokens":119,"total_tokens":13286}}}}\n'
                '{"timestamp":"2026-08-02T04:55:23Z","type":"event_msg","payload":'
                '{"type":"token_count","info":{"total_token_usage":{"input_tokens":14167,'
                '"cached_input_tokens":600,"output_tokens":169,"total_tokens":14336}}}}\n',
                encoding="utf-8",
            )
            _, _, records = parse_session_file(f)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[1].input_tokens, 1000)
            self.assertEqual(records[1].cached_input_tokens, 600)
            self.assertEqual(records[1].output_tokens, 50)
            self.assertEqual(records[1].total_tokens, 1050)

class TestScan(unittest.TestCase):
    def test_dedup_and_thread_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = _write_session(root)
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(
                    '{"timestamp":"2026-08-02T04:55:23.046Z","type":"event_msg",'
                    '"payload":{"type":"token_count","info":{"last_token_usage":'
                    '{"input_tokens":1000,"cached_input_tokens":600,'
                    '"output_tokens":50,"total_tokens":1050}}}}\n'
                )
            (root / "session_index.jsonl").write_text(
                '{"id":"s1","thread_name":"我的项目"}\n', encoding="utf-8"
            )
            records = scan_codex_sessions(root)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].thread_name, "我的项目")
            self.assertLess(records[0].event_time, records[1].event_time)


class TestExport(unittest.TestCase):
    def test_export_json_structure(self):
        with tempfile.TemporaryDirectory() as td:
            _write_session(Path(td))
            data = export_json(scan_codex_sessions(Path(td)))
            self.assertEqual(data["source"], "codex")
            self.assertEqual(len(data["records"]), 2)
            self.assertIn("key", data["records"][0])
            self.assertIn("cache_miss_tokens", data["records"][0])


class TestSyncToDb(unittest.TestCase):
    def setUp(self):
        import modelbalance.storage as storage

        self._tmp = tempfile.TemporaryDirectory()
        self._codex_dir = Path(self._tmp.name) / "codex"
        _write_session(self._codex_dir)
        self._orig_data = storage.DATA_DIR
        self._orig_db = storage.DB_PATH
        storage.DATA_DIR = Path(self._tmp.name) / "db"
        storage.DB_PATH = storage.DATA_DIR / "test.db"

    def tearDown(self):
        import modelbalance.storage as storage

        storage.DATA_DIR = self._orig_data
        storage.DB_PATH = self._orig_db
        self._tmp.cleanup()

    def test_sync_adds_and_dedups(self):
        from modelbalance.storage import list_usage_records

        added = sync_codex_usage_to_db(self._codex_dir)
        self.assertEqual(added, 2)
        records = list_usage_records(account="codex")
        self.assertEqual(len(records), 2)

        # 第二次同步应全部跳过
        added_again = sync_codex_usage_to_db(self._codex_dir)
        self.assertEqual(added_again, 0)
        self.assertEqual(len(list_usage_records(account="codex")), 2)


if __name__ == "__main__":
    unittest.main()
