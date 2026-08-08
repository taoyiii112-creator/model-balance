"""便捷入口：python run.py balance；也是 PyInstaller 打包入口。"""
from __future__ import annotations

import os
import shutil
import sys
import traceback
from pathlib import Path


def _prepare_tcl_tk() -> None:
    """Tcl 8.6 在含中文的绝对路径下无法读取 init.tcl（如 C:\\Users\\小张\\...），
    把 Tcl/Tk 数据复制到纯 ASCII 路径并设置 TCL_LIBRARY / TK_LIBRARY，
    否则打包版/源码版都无法创建 Tk 窗口。
    """
    try:
        if getattr(sys, "frozen", False):
            src_tcl = Path(getattr(sys, "_MEIPASS", "")) / "_tcl_data"
            src_tk = Path(getattr(sys, "_MEIPASS", "")) / "_tk_data"
        else:
            base = Path(sys.base_prefix)
            src_tcl = base / "tcl" / "tcl8.6"
            src_tk = base / "tcl" / "tk8.6"
        if not src_tcl.is_dir() or not src_tk.is_dir():
            return

        candidates = [
            Path("D:/codexProject/mb_tcl_stage"),
            Path("C:/Users/Public/mb_tcl_stage"),
            Path(os.environ.get("SystemDrive", "C:") + "/mb_tcl_stage"),
        ]
        for dst_root in candidates:
            try:
                dst_root.mkdir(parents=True, exist_ok=True)
                dst_root.as_posix().encode("ascii")
            except (OSError, UnicodeEncodeError):
                continue
            dst_tcl = dst_root / "tcl8.6"
            dst_tk = dst_root / "tk8.6"
            try:
                if not (dst_tcl / "init.tcl").exists():
                    shutil.copytree(src_tcl, dst_tcl, dirs_exist_ok=True)
                if not (dst_tk / "ttk").is_dir():
                    shutil.copytree(src_tk, dst_tk, dirs_exist_ok=True)
            except OSError:
                continue
            os.environ["TCL_LIBRARY"] = str(dst_tcl)
            os.environ["TK_LIBRARY"] = str(dst_tk)
            return
    except Exception:  # noqa: BLE001 - 兜底：失败则维持默认，交给 Tk 报错
        pass


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
    _prepare_tcl_tk()
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
