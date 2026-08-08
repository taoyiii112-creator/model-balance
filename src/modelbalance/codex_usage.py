"""从 Codex 本地会话记录提取真实 Token 用量。

数据来源：~/.codex/sessions 与 ~/.codex/archived_sessions 下的 rollout JSONL。
每个 event_msg（payload.type == "token_count"）代表一轮调用的用量：
  - cached_input_tokens        → 输入（命中缓存）
  - input_tokens - cached      → 输入（未命中缓存）
  - output_tokens              → 输出
  - total_tokens               → 总 Token
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CodexUsageRecord:
    """单次调用的用量（last_token_usage 增量）。"""

    session_id: str
    event_time: datetime
    thread_name: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int

    @property
    def cache_miss_tokens(self) -> int:
        return self.input_tokens - self.cached_input_tokens

    @property
    def key(self) -> str:
        """去重键：会话 id + 事件时间（秒精度）。"""
        ts = self.event_time.astimezone().isoformat(timespec="seconds")
        return f"{self.session_id}:{ts}"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "session": self.session_id,
            "thread": self.thread_name,
            "created_at": self.event_time.astimezone().isoformat(),
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_miss_tokens": self.cache_miss_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now()


def parse_session_file(path: Path) -> tuple[str, str, list[CodexUsageRecord]]:
    """解析单个 rollout JSONL，返回 (session_id, cwd, 用量记录列表)。"""
    session_id = path.stem
    cwd = ""
    records: list[CodexUsageRecord] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            obj_type = obj.get("type")
            if obj_type == "session_meta":
                payload = obj.get("payload") or {}
                session_id = payload.get("session_id") or payload.get("id") or session_id
                cwd = payload.get("cwd") or ""
                continue
            if obj_type != "event_msg":
                continue
            payload = obj.get("payload") or {}
            if payload.get("type") != "token_count":
                continue
            info = payload.get("info") or {}
            usage = info.get("last_token_usage") or {}
            if not usage:
                continue
            records.append(
                CodexUsageRecord(
                    session_id=session_id,
                    event_time=_parse_time(obj.get("timestamp") or ""),
                    thread_name="",
                    input_tokens=int(usage.get("input_tokens") or 0),
                    cached_input_tokens=int(usage.get("cached_input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                    total_tokens=int(usage.get("total_tokens") or 0),
                )
            )
    return session_id, cwd, records


def load_session_index(codex_dir: Path) -> dict[str, str]:
    """session_index.jsonl：session_id -> thread_name。"""
    index: dict[str, str] = {}
    path = codex_dir / "session_index.jsonl"
    if not path.exists():
        return index
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = obj.get("id")
        if sid:
            index[sid] = obj.get("thread_name") or sid
    return index


def scan_codex_sessions(codex_dir: Path | None = None) -> list[CodexUsageRecord]:
    """扫描全部会话文件，按 key 去重后按时间升序返回。"""
    codex_dir = codex_dir or Path.home() / ".codex"
    index = load_session_index(codex_dir)
    by_key: dict[str, CodexUsageRecord] = {}
    for root in (codex_dir / "sessions", codex_dir / "archived_sessions"):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.jsonl")):
            session_id, cwd, records = parse_session_file(path)
            thread = index.get(session_id) or Path(cwd).name or "codex"
            for rec in records:
                rec.session_id = session_id
                rec.thread_name = thread
                by_key[rec.key] = rec
    return sorted(by_key.values(), key=lambda r: r.event_time)


def export_json(records: list[CodexUsageRecord]) -> dict:
    """生成手机端可导入的 JSON。"""
    return {
        "source": "codex",
        "generated_at": datetime.now().astimezone().isoformat(),
        "records": [r.to_dict() for r in records],
    }
