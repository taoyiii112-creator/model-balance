"""应用更新：检查 GitHub Releases、下载更新包、应用更新。

更新源为 GitHub Releases（仓库见 GITHUB_OWNER / GITHUB_REPO）。
网络访问：api.github.com 查询最新版本；github.com / objects.githubusercontent.com 下载更新包。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError

from .config import PROJECT_ROOT

GITHUB_OWNER = "taoyiii112-creator"
GITHUB_REPO = "model-balance"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
UPDATE_SOURCE_FILE = PROJECT_ROOT / "data" / "update_source.json"


def get_update_source() -> str:
    """当前更新源：优先环境变量 MB_UPDATE_SOURCE，其次 data/update_source.json，最后默认 GitHub。"""
    url = os.environ.get("MB_UPDATE_SOURCE", "").strip()
    if url:
        return url
    try:
        if UPDATE_SOURCE_FILE.exists():
            data = json.loads(UPDATE_SOURCE_FILE.read_text(encoding="utf-8"))
            url = (data.get("url") or "").strip()
            if url:
                return url
    except (OSError, ValueError):
        pass
    return RELEASE_API


def set_update_source(url: str) -> None:
    """设置自定义更新源；传空字符串恢复默认 GitHub Releases。"""
    url = url.strip()
    if not url:
        UPDATE_SOURCE_FILE.unlink(missing_ok=True)
        return
    UPDATE_SOURCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_SOURCE_FILE.write_text(
        json.dumps({"url": url}, ensure_ascii=False), encoding="utf-8"
    )
SKIP_ON_APPLY = {".env", "data", "config.json", ".git", "dist", "__pycache__", ".pytest_cache", ".idea", ".vscode"}


def parse_version(v: str) -> tuple:
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", v)
    if not match:
        return (0,)
    return tuple(int(g) for g in match.groups() if g is not None)


def is_newer(local: str, remote: str) -> bool:
    return parse_version(remote) > parse_version(local)


def fmt_size(num_bytes: int) -> str:
    mb = num_bytes / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{num_bytes / 1024:.0f} KB"


def parse_release(data: dict) -> dict | None:
    """从 GitHub Releases API 响应中提取更新信息（zip 资产）。"""
    asset = next((a for a in data.get("assets", []) if a.get("name", "").endswith(".zip")), None)
    if not data.get("tag_name") or not asset:
        return None
    return {
        "tag_name": data.get("tag_name", ""),
        "name": data.get("name", ""),
        "body": (data.get("body") or "").strip(),
        "published_at": data.get("published_at", ""),
        "asset_name": asset.get("name", ""),
        "asset_size": int(asset.get("size") or 0),
        "asset_url": asset.get("browser_download_url", ""),
    }


def fetch_latest_release(source_url: str | None = None, timeout: int = 20) -> dict | None:
    """获取最新 Release；无 Release 返回 None，网络异常抛出。"""
    url = source_url or get_update_source()
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "model-balance-updater"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return parse_release(data)


def check_for_update(current_version: str) -> dict | None:
    """有可用更新时返回更新信息，否则返回 None（无 Release / 已是最新）。"""
    info = fetch_latest_release()
    if not info or not info.get("asset_url"):
        return None
    if not is_newer(current_version, info["tag_name"]):
        return None
    return info


def download_asset(url: str, dest: Path, progress_cb=None) -> Path:
    """下载更新包到 dest，通过 progress_cb(已下载, 总量) 报告进度。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "model-balance-updater"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        tmp = dest.with_suffix(dest.suffix + ".part")
        done = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
        tmp.replace(dest)
    validate_zip(dest)
    return dest


def validate_zip(path: Path) -> None:
    """校验更新包是可用的 zip（含 CRC 检查）。"""
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"更新包校验失败: {bad}")


def cleanup_updates(updates_dir: Path = PROJECT_ROOT / "data" / "updates", keep: Path | None = None) -> None:
    """清理下载的更新包（默认全部清理，可保留指定文件）。"""
    if not updates_dir.exists():
        return
    for f in updates_dir.iterdir():
        if f.is_file() and f != keep:
            try:
                f.unlink()
            except OSError:
                pass


def apply_update(zip_path: Path, app_dir: Path = PROJECT_ROOT) -> None:
    """解压更新包并覆盖应用文件（保留 .env / data / config.json 等用户数据）。"""
    with tempfile.TemporaryDirectory() as td:
        extract_to = Path(td)
        shutil.unpack_archive(str(zip_path), str(extract_to), "zip")
        for item in extract_to.iterdir():
            if item.name in SKIP_ON_APPLY:
                continue
            dest = app_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)


def relaunch_app() -> None:
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    target = pyw if pyw.exists() else exe
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [str(target), str(PROJECT_ROOT / "run.py"), "app"],
        cwd=str(PROJECT_ROOT),
        creationflags=flags,
    )