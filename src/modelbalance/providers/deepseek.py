"""DeepSeek 余额查询。

接口：GET https://api.deepseek.com/user/balance
返回示例：
{
  "is_available": true,
  "balance_infos": [
    {"currency": "CNY", "total_balance": "110.00",
     "granted_balance": "10.00", "topped_up_balance": "100.00"}
  ]
}
"""
from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from ..models import Balance
from .base import Provider, ProviderError

BALANCE_URL = "https://api.deepseek.com/user/balance"


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def parse_balance(account_name: str, data: dict) -> Balance:
    if not data.get("is_available"):
        raise ProviderError(f"DeepSeek 账户不可用: {data}")
    infos = data.get("balance_infos") or []
    total = granted = topped = None
    currency = "CNY"
    if infos:
        info = infos[0]
        total = _to_float(info.get("total_balance"))
        granted = _to_float(info.get("granted_balance"))
        topped = _to_float(info.get("topped_up_balance"))
        currency = info.get("currency") or currency
    return Balance(
        account=account_name,
        provider="deepseek",
        currency=currency,
        available=total,
        total=total,
        granted=granted,
        topped_up=topped,
        raw=data,
    )


class DeepSeekProvider(Provider):
    name = "deepseek"

    def fetch_balance(self) -> Balance:
        req = request.Request(
            BALANCE_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, OSError) as exc:
            raise ProviderError(f"DeepSeek 余额请求失败: {exc}") from exc
        return parse_balance(self.account_name, data)