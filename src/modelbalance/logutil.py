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
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger