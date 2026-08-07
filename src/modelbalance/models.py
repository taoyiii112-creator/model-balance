"""核心数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Balance:
    account: str
    provider: str
    currency: str = "CNY"
    available: float | None = None       # 可用金额
    total: float | None = None           # 总额
    used: float | None = None            # 已使用金额
    granted: float | None = None         # 赠送金额
    topped_up: float | None = None       # 充值金额
    raw: dict = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.now)

    @property
    def ok(self) -> bool:
        return self.available is not None or self.total is not None


@dataclass
class UsageRecord:
    account: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    prompt_cache_hit_tokens: int = 0      # 输入（命中缓存）
    prompt_cache_miss_tokens: int = 0     # 输入（未命中缓存）
    cost: float | None = None
    note: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens