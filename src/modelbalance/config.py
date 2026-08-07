"""配置加载：.env 环境变量 + config.json 账户清单。"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：数据/配置放在 exe 同目录，保证持久化
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_env(env_path: Path | None = None) -> None:
    """把 .env 中的 KEY=VALUE 载入环境变量（已存在的环境变量优先）。"""
    env_file = env_path or PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Account:
    name: str
    provider: str
    api_key_env: str
    base_url: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "").strip()


def load_accounts(config_path: Path | None = None) -> list[Account]:
    """从 config.json 读取账户清单。"""
    cfg_path = config_path or PROJECT_ROOT / "config.json"
    if not cfg_path.exists():
        return []
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    accounts = []
    for item in data.get("accounts", []):
        accounts.append(
            Account(
                name=item["name"],
                provider=item["provider"],
                api_key_env=item.get("api_key_env", ""),
                base_url=item.get("base_url"),
                extra=item.get("extra", {}) or {},
            )
        )
    return accounts