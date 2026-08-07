"""极简日志：写入 data/logs/app.log。"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import PROJECT_ROOT

_configured = False


def get_logger(name: str = "modelbalance") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        _configured = True
        log_dir = PROJECT_ROOT / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        # 挂到 root：所有模块的 logger 都会写入同一个文件
        root = logging.getLogger()
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logger