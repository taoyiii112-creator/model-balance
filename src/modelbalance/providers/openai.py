"""OpenAI 官方余额查询。

接口：GET https://api.openai.com/v1/dashboard/billing/credit_grants
返回示例：{"total_granted": 100.0, "total_used": 30.0, "total_available": 70.0}

注意：该接口历史上对部分 API Key 不稳定（曾要求会话 Cookie），
若返回 401/404 说明当前 Key 无权访问，可改用中转渠道方式接入。
"""
from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from ..models import Balance
from .base import Provider, ProviderError

BALANCE_URL = "https://api.openai.com/v1/dashboard/billing/credit_grants"


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def parse_balance(account_name: str, payload: dict) -> Balance:
    total_granted = _to_float(payload.get("total_granted"))
    total_used = _to_float(payload.get("total_used"))
    total_available = _to_float(payload.get("total_available"))
    if total_available is None and total_granted is None:
        raise ProviderError(f"OpenAI 余额响应缺少金额字段: {payload}")
    return Balance(
        account=account_name,
        provider="openai",
        currency="USD",
        available=total_available,
        total=total_granted,
        used=total_used,
        raw=payload,
    )


class OpenAIProvider(Provider):
    name = "openai"

    def fetch_balance(self) -> Balance:
        req = request.Request(
            BALANCE_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, OSError) as exc:
            raise ProviderError(f"OpenAI 余额请求失败: {exc}") from exc
        return parse_balance(self.account_name, payload)