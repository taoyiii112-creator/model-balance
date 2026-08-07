"""用 PyInstaller 打包桌面应用为单文件 exe（dist/model-balance.exe）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "model-balance",
        "--paths", str(ROOT / "src"),
        "--hidden-import", "modelbalance",
        "--hidden-import", "modelbalance.cli",
        "--hidden-import", "modelbalance.app",
        "--hidden-import", "modelbalance.web",
        "--hidden-import", "modelbalance.proxy",
        "--hidden-import", "modelbalance.updater",
        "--hidden-import", "modelbalance.storage",
        "--hidden-import", "modelbalance.logutil",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        str(ROOT / "run.py"),
    ]
    print("运行:", " ".join(cmd))
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())