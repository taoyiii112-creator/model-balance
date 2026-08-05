"""本地 SQLite 存储：余额快照 + Token 用量记录。"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .models import Balance, UsageRecord

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
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
    note TEXT DEFAULT ''
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
    return conn


def _db():
    return closing(_connect())


def init_db() -> None:
    with _db() as conn:
        conn.executescript(SCHEMA)


def add_usage_record(rec: UsageRecord) -> int:
    init_db()
    with _db() as conn:
        cur = conn.execute(
            """INSERT INTO usage_records
               (account, model, created_at, prompt_tokens, completion_tokens, total_tokens, cost, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.account,
                rec.model,
                rec.created_at.isoformat(timespec="seconds"),
                rec.prompt_tokens,
                rec.completion_tokens,
                rec.total_tokens,
                rec.cost,
                rec.note,
            ),
        )
        return cur.lastrowid


def list_usage_records(account: str | None = None, since: datetime | None = None) -> list[dict]:
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
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    with _db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def usage_totals(account: str | None = None, since: datetime | None = None) -> dict:
    """汇总 Token 与费用。"""
    records = list_usage_records(account, since)
    return {
        "records": len(records),
        "prompt_tokens": sum(r["prompt_tokens"] for r in records),
        "completion_tokens": sum(r["completion_tokens"] for r in records),
        "total_tokens": sum(r["total_tokens"] for r in records),
        "cost": sum(r["cost"] or 0 for r in records),
    }


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