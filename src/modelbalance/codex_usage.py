"""从 Codex 本地会话记录提取真实 Token 用量。

数据来源：~/.codex/sessions 与 ~/.codex/archived_sessions 下的 rollout JSONL。
每个 event_msg（payload.type == "token_count"）代表一轮调用：
  - 优先按会话累计值 total_token_usage 取增量（当前值 - 上一值），保证求和 = 会话真实总量
  - total_token_usage 缺失时回退到 last_token_usage（视为单轮增量）
拆分：
  - cached_input_tokens   → 输入（命中缓存）
  - input_tokens - cached → 输入（未命中缓存）
  - output_tokens         → 输出
  - total_tokens          → 总 Token
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    prev_total: tuple[int, int, int, int] | None = None
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
            total = info.get("total_token_usage") or {}
            last = info.get("last_token_usage") or {}
            if total:
                cur = (
                    int(total.get("input_tokens") or 0),
                    int(total.get("cached_input_tokens") or 0),
                    int(total.get("output_tokens") or 0),
                    int(total.get("total_tokens") or 0),
                )
                if prev_total is None:
                    delta = cur
                else:
                    # 取增量；若累计值回退（换会话/重置），以当前值为准
                    delta = tuple(
                        (c - p) if c >= p else c for c, p in zip(cur, prev_total)
                    )
                prev_total = cur
            elif last:
                delta = (
                    int(last.get("input_tokens") or 0),
                    int(last.get("cached_input_tokens") or 0),
                    int(last.get("output_tokens") or 0),
                    int(last.get("total_tokens") or 0),
                )
            else:
                continue
            if delta[3] <= 0 and delta[0] <= 0 and delta[2] <= 0:
                continue
            records.append(
                CodexUsageRecord(
                    session_id=session_id,
                    event_time=_parse_time(obj.get("timestamp") or ""),
                    thread_name="",
                    input_tokens=delta[0],
                    cached_input_tokens=delta[1],
                    output_tokens=delta[2],
                    total_tokens=delta[3],
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


def sync_codex_usage_to_db(codex_dir: Path | None = None, keep_days: int = 14) -> int:
    """扫描 Codex 会话并增量写入本地用量库，随后清理超过 keep_days 的旧记录。

    返回本次新增条数。仅写入 keep_days 内的记录，避免清理后旧记录反复回填。
    """
    from .models import UsageRecord
    from .storage import (
        add_usage_records_many,
        existing_codex_notes,
        init_db,
        prune_usage_records,
    )

    init_db()
    cutoff = datetime.now().astimezone() - timedelta(days=keep_days)
    records = scan_codex_sessions(codex_dir)
    existing = existing_codex_notes()
    to_add: list[UsageRecord] = []
    for r in records:
        if r.event_time.astimezone() < cutoff:
            continue
        note = f"codex:{r.key}"
        if note in existing:
            continue
        to_add.append(
            UsageRecord(
                account="codex",
                model="codex",
                prompt_tokens=r.input_tokens,
                completion_tokens=r.output_tokens,
                prompt_cache_hit_tokens=r.cached_input_tokens,
                prompt_cache_miss_tokens=r.cache_miss_tokens,
                note=note,
                created_at=r.event_time.astimezone(),  # 统一存本地时间，避免显示 UTC
            )
        )
    added = add_usage_records_many(to_add) if to_add else 0
    prune_usage_records(keep_days)
    return added
