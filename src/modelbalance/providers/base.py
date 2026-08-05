"""Provider 抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Balance


class ProviderError(RuntimeError):
    pass


class Provider(ABC):
    name: str = "base"

    def __init__(self, account_name: str, api_key: str, base_url: str | None = None, **kwargs):
        self.account_name = account_name
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def fetch_balance(self) -> Balance:
        """查询账户余额，失败时抛出 ProviderError。"""