"""Provider 注册与工厂。"""
from __future__ import annotations

from ..config import Account
from .base import Provider, ProviderError
from .deepseek import DeepSeekProvider
from .openai import OpenAIProvider
from .openai_compat import OpenAICompatProvider

REGISTRY: dict[str, type[Provider]] = {
    DeepSeekProvider.name: DeepSeekProvider,
    OpenAIProvider.name: OpenAIProvider,
    OpenAICompatProvider.name: OpenAICompatProvider,
}


def create_provider(account: Account) -> Provider:
    cls = REGISTRY.get(account.provider)
    if cls is None:
        raise ProviderError(
            f"未知的 provider 类型: {account.provider}（可用: {', '.join(REGISTRY)}）"
        )
    if not account.api_key:
        raise ProviderError(
            f"账户 {account.name} 缺少 API Key（环境变量 {account.api_key_env} 未设置）"
        )
    return cls(
        account_name=account.name,
        api_key=account.api_key,
        base_url=account.base_url,
        **account.extra,
    )