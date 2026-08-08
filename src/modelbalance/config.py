"""配置加载：.env 环境变量 + config.json 账户清单。"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：优先使用"exe 上级目录 = 项目根"（自用/开发场景），
    # 否则回退到 exe 同目录（对外分发场景，配置放 exe 旁边）。
    exe_dir = Path(sys.executable).resolve().parent
    parent = exe_dir.parent
    if (parent / "config.json").exists() or (parent / ".env").exists() or (parent / "src").exists():
        PROJECT_ROOT = parent
    else:
        PROJECT_ROOT = exe_dir
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


DEFAULT_ALERT_THRESHOLD = 5.0


def load_settings(config_path: Path | None = None) -> dict:
    """读取 config.json 顶层设置（当前仅 alert_threshold），缺失或非法时用默认值。"""
    cfg_path = config_path or PROJECT_ROOT / "config.json"
    threshold = DEFAULT_ALERT_THRESHOLD
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        try:
            threshold = float(data.get("alert_threshold", DEFAULT_ALERT_THRESHOLD))
        except (TypeError, ValueError):
            threshold = DEFAULT_ALERT_THRESHOLD
    return {"alert_threshold": max(0.0, threshold)}


def save_setting(key: str, value, config_path: Path | None = None) -> bool:
    """把顶层设置写回 config.json（保留 accounts）；文件不存在或写入失败返回 False。"""
    cfg_path = config_path or PROJECT_ROOT / "config.json"
    try:
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            data = {}
        data[key] = value
        cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except (OSError, ValueError):
        return False


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