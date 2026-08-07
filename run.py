"""便捷入口：python run.py balance；也是 PyInstaller 打包入口。"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


def _write_crash() -> None:
    try:
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).resolve().parent
        else:
            base = Path(__file__).resolve().parent
        log_dir = base / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "crash.log").write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


def _main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from modelbalance.cli import main

    return main()


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except SystemExit:
        raise
    except Exception:
        _write_crash()
        raise