"""应用暂存更新：等待主应用退出后，把暂存目录覆盖到应用目录并重启。

用法: python apply_staged.py <主应用PID>
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGING = ROOT / "data" / "update_staging"
SKIP = {".env", "data", "config.json", ".git", "dist", "__pycache__", ".pytest_cache", ".idea", ".vscode"}


def is_alive(pid: int) -> bool:
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True, timeout=10,
        )
        return str(pid) in r.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def apply_staging() -> bool:
    if not STAGING.exists():
        print("没有待应用的更新")
        return False
    for item in STAGING.iterdir():
        if item.name in SKIP:
            continue
        dest = ROOT / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
    shutil.rmtree(STAGING, ignore_errors=True)
    print("更新已应用")
    return True


def relaunch() -> None:
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    target = pyw if pyw.exists() else exe
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [str(target), str(ROOT / "run.py"), "app"],
        cwd=str(ROOT),
        creationflags=flags,
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python apply_staged.py <主应用PID>")
        return 1
    pid = int(sys.argv[1])
    deadline = time.time() + 90
    while time.time() < deadline:
        if not is_alive(pid):
            break
        time.sleep(1)
    apply_staging()
    relaunch()
    return 0


if __name__ == "__main__":
    sys.exit(main())