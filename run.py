"""便捷入口：python run.py balance"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from modelbalance.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())