"""OpenAI 兼容中转渠道（one-api / new-api 类）余额查询。

约定接口：GET {base_url}/api/user/status
返回示例：{"data": {"quota": 8000000, "used_quota": 2000000}}
one-api 的 quota 单位：1 quota = 1/500000（默认）美元/人民币，按渠道配置。
可通过账户 extra 配置：
- quota_denominator：换算分母，默认 500000
- quota_currency：币种，默认 CNY
"""
from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from ..models import Balance
from .base import Provider, ProviderError

DEFAULT_QUOTA_DENOMINATOR = 500_000.0


def parse_balance(account_name: str, payload: dict, denominator: float, currency: str) -> Balance:
    data = payload.get("data") or {}
    quota = data.get("quota")
    used_quota = data.get("used_quota")
    available = quota / denominator if quota is not None else None
    used = used_quota / denominator if used_quota is not None else None
    return Balance(
        account=account_name,
        provider="openai_compat",
        currency=currency,
        available=available,
        used=used,
        raw=payload,
    )


class OpenAICompatProvider(Provider):
    name = "openai_compat"

    def __init__(self, account_name: str, api_key: str, base_url: str | None = None, **kwargs):
        super().__init__(account_name, api_key, base_url, **kwargs)
        self.quota_denominator = float(kwargs.get("quota_denominator", DEFAULT_QUOTA_DENOMINATOR))
        self.quota_currency = kwargs.get("quota_currency", "CNY")

    def fetch_balance(self) -> Balance:
        if not self.base_url:
            raise ProviderError("openai_compat 需要配置 base_url")
        url = self.base_url.rstrip("/") + "/api/user/status"
        req = request.Request(url, headers={"Authorization": f"Bearer {self.api_key}"})
        try:
            with request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, OSError) as exc:
            raise ProviderError(f"中转渠道余额请求失败: {exc}") from exc
        return parse_balance(self.account_name, payload, self.quota_denominator, self.quota_currency)