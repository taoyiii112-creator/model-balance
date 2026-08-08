"""本地 SQLite 存储：余额快照 + Token 用量记录。"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from .config import PROJECT_ROOT
from .models import Balance, UsageRecord

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "balance.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost REAL,
    note TEXT DEFAULT '',
    prompt_cache_hit_tokens INTEGER NOT NULL DEFAULT 0,
    prompt_cache_miss_tokens INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS balance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    provider TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'CNY',
    available REAL,
    total REAL,
    used REAL,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None)  # 自动提交模式
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _db():
    return closing(_connect())


def init_db() -> None:
    with _db() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
    prune_usage_records()  # 用量记录只保留 14 天


def _migrate(conn: sqlite3.Connection) -> None:
    """旧库补充新增列（幂等）。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(usage_records)")}
    if "prompt_cache_hit_tokens" not in cols:
        conn.execute("ALTER TABLE usage_records ADD COLUMN prompt_cache_hit_tokens INTEGER NOT NULL DEFAULT 0")
    if "prompt_cache_miss_tokens" not in cols:
        conn.execute("ALTER TABLE usage_records ADD COLUMN prompt_cache_miss_tokens INTEGER NOT NULL DEFAULT 0")


def add_usage_record(rec: UsageRecord) -> int:
    init_db()
    with _db() as conn:
        cur = conn.execute(
            """INSERT INTO usage_records
               (account, model, created_at, prompt_tokens, completion_tokens, total_tokens,
                cost, note, prompt_cache_hit_tokens, prompt_cache_miss_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.account,
                rec.model,
                rec.created_at.isoformat(timespec="seconds"),
                rec.prompt_tokens,
                rec.completion_tokens,
                rec.total_tokens,
                rec.cost,
                rec.note,
                rec.prompt_cache_hit_tokens,
                rec.prompt_cache_miss_tokens,
            ),
        )
        return cur.lastrowid


def add_usage_records_many(records: list[UsageRecord]) -> int:
    """批量写入用量记录（单事务），返回写入条数。调用方需先 init_db。"""
    if not records:
        return 0
    with _db() as conn:
        cur = conn.executemany(
            """INSERT INTO usage_records
               (account, model, created_at, prompt_tokens, completion_tokens, total_tokens,
                cost, note, prompt_cache_hit_tokens, prompt_cache_miss_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    rec.account,
                    rec.model,
                    rec.created_at.isoformat(timespec="seconds"),
                    rec.prompt_tokens,
                    rec.completion_tokens,
                    rec.total_tokens,
                    rec.cost,
                    rec.note,
                    rec.prompt_cache_hit_tokens,
                    rec.prompt_cache_miss_tokens,
                )
                for rec in records
            ],
        )
        return cur.rowcount


def existing_codex_notes() -> set[str]:
    """返回已入库的 codex 记录 note（用于增量去重）。"""
    init_db()
    with _db() as conn:
        rows = conn.execute(
            "SELECT note FROM usage_records WHERE note LIKE 'codex:%'"
        ).fetchall()
        return {r[0] for r in rows}


def list_usage_records(
    account: str | None = None,
    since: datetime | None = None,
    exclude: str | None = None,
) -> list[dict]:
    init_db()
    sql = "SELECT * FROM usage_records"
    clauses: list[str] = []
    params: list = []
    if account:
        clauses.append("account = ?")
        params.append(account)
    if since:
        clauses.append("created_at >= ?")
        params.append(since.isoformat(timespec="seconds"))
    if exclude:
        clauses.append("account != ?")
        params.append(exclude)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    with _db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def usage_totals(
    account: str | None = None,
    since: datetime | None = None,
    exclude: str | None = None,
) -> dict:
    """汇总 Token 与费用。"""
    records = list_usage_records(account, since, exclude)
    return {
        "records": len(records),
        "prompt_tokens": sum(r["prompt_tokens"] for r in records),
        "completion_tokens": sum(r["completion_tokens"] for r in records),
        "total_tokens": sum(r["total_tokens"] for r in records),
        "prompt_cache_hit_tokens": sum(r["prompt_cache_hit_tokens"] for r in records),
        "prompt_cache_miss_tokens": sum(r["prompt_cache_miss_tokens"] for r in records),
        "cost": sum(r["cost"] or 0 for r in records),
    }


def usage_daily(account: str | None = None, days: int = 30, exclude: str | None = None) -> list[dict]:
    """按天聚合消费金额与 Token 数（含无数据的零值天），用于柱状图。"""
    init_db()
    days = max(1, days)
    start = (datetime.now() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    sql = """SELECT substr(created_at, 1, 10) AS day,
                    SUM(cost) AS cost, SUM(total_tokens) AS tokens
             FROM usage_records WHERE created_at >= ?"""
    params: list = [start.isoformat(timespec="seconds")]
    if account:
        sql += " AND account = ?"
        params.append(account)
    if exclude:
        sql += " AND account != ?"
        params.append(exclude)
    sql += " GROUP BY day ORDER BY day"
    with _db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    by_day = {r["day"]: r for r in rows}
    result = []
    for i in range(days):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        r = by_day.get(day)
        result.append(
            {
                "day": day,
                "cost": round(float(r["cost"] or 0), 4) if r else 0.0,
                "tokens": int(r["tokens"] or 0) if r else 0,
            }
        )
    return result


def usage_breakdown(
    account: str | None = None,
    since: datetime | None = None,
    exclude: str | None = None,
) -> dict:
    """Token 构成：输入(命中缓存) / 输入(未命中缓存) / 输出，用于扇形图。"""
    init_db()
    sql = """SELECT COALESCE(SUM(prompt_cache_hit_tokens), 0) AS hit,
                    COALESCE(SUM(prompt_cache_miss_tokens), 0) AS miss,
                    COALESCE(SUM(completion_tokens), 0) AS output
             FROM usage_records"""
    clauses: list[str] = []
    params: list = []
    if account:
        clauses.append("account = ?")
        params.append(account)
    if since:
        clauses.append("created_at >= ?")
        params.append(since.isoformat(timespec="seconds"))
    if exclude:
        clauses.append("account != ?")
        params.append(exclude)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with _db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, params).fetchone()
    return {
        "cache_hit": int(row["hit"]),
        "cache_miss": int(row["miss"]),
        "output": int(row["output"]),
    }


def prune_usage_records(keep_days: int = 14) -> int:
    """删除超过 keep_days 的用量记录，返回删除条数（调用方需先 init_db）。"""
    cutoff = (datetime.now() - timedelta(days=keep_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    with _db() as conn:
        cur = conn.execute(
            "DELETE FROM usage_records WHERE created_at < ?",
            (cutoff.isoformat(timespec="seconds"),),
        )
        return cur.rowcount


def snapshot_history(account: str | None = None, days: int = 30) -> list[dict]:
    """余额快照历史（按时间升序），用于趋势图。"""
    init_db()
    start = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    sql = "SELECT account, provider, currency, available, total, used, created_at FROM balance_snapshots WHERE created_at >= ?"
    params: list = [start.isoformat(timespec="seconds")]
    if account:
        sql += " AND account = ?"
        params.append(account)
    sql += " ORDER BY created_at ASC"
    with _db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def add_snapshot(balance: Balance) -> int:
    init_db()
    with _db() as conn:
        cur = conn.execute(
            """INSERT INTO balance_snapshots
               (account, provider, currency, available, total, used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                balance.account,
                balance.provider,
                balance.currency,
                balance.available,
                balance.total,
                balance.used,
                balance.fetched_at.isoformat(timespec="seconds"),
            ),
        )
        return cur.lastrowid


def latest_snapshots() -> list[dict]:
    init_db()
    with _db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT s.* FROM balance_snapshots s
               JOIN (SELECT account, MAX(created_at) AS m FROM balance_snapshots GROUP BY account) t
                 ON s.account = t.account AND s.created_at = t.m
               ORDER BY s.account"""
        ).fetchall()
        return [dict(r) for r in rows]
