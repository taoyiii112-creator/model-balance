"""用 PyInstaller 打包桌面应用为单文件 exe（dist/model-balance.exe）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _stage_tcl_tk() -> None:
    """把 Python 自带的 Tcl/Tk 数据目录复制到纯 ASCII 路径并设置环境变量。

    中文用户名路径（如 C:\\Users\\小张\\...）会导致 Tcl 找不到 init.tcl，
    PyInstaller 检测失败后会把 tkinter 排除，exe 将无法打开窗口。
    """
    base = Path(sys.base_prefix)
    src_tcl = base / "tcl" / "tcl8.6"
    src_tk = base / "tcl" / "tk8.6"
    stage = ROOT.parent / "mb_tcl_stage"
    dst_tcl = stage / "tcl8.6"
    dst_tk = stage / "tk8.6"
    if not src_tcl.is_dir() or not src_tk.is_dir():
        return
    stage.mkdir(parents=True, exist_ok=True)
    if not dst_tcl.is_dir():
        shutil.copytree(src_tcl, dst_tcl)
    if not dst_tk.is_dir():
        shutil.copytree(src_tk, dst_tk)
    os.environ["TCL_LIBRARY"] = str(dst_tcl)
    os.environ["TK_LIBRARY"] = str(dst_tk)
    print(f"Tcl/Tk 已暂存: {stage}")


def main() -> int:
    _stage_tcl_tk()
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
