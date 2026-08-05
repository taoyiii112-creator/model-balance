"""余额聚合查询。"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Account
from .models import Balance


@dataclass
class AccountResult:
    account: Account
    balance: Balance | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.balance is not None


def fetch_one(account: Account) -> AccountResult:
    from .providers import create_provider
    from .providers.base import ProviderError

    try:
        provider = create_provider(account)
        balance = provider.fetch_balance()
        return AccountResult(account=account, balance=balance)
    except ProviderError as exc:
        return AccountResult(account=account, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - 单个账户失败不阻断其他账户
        return AccountResult(account=account, error=f"{type(exc).__name__}: {exc}")


def fetch_all(accounts: list[Account]) -> list[AccountResult]:
    return [fetch_one(acc) for acc in accounts]