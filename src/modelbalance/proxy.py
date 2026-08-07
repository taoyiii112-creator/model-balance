"""本地 OpenAI 兼容 API 代理：转发请求并自动记录 Token 用量。

用法：把客户端的 base_url 指向本机代理（如 http://127.0.0.1:8001/v1），
API Key 保持原样（必须是 config.json 已配置账户的 Key）。
所有请求经由此代理转发到真实上游，并自动把 usage 写入本地数据库。
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .config import PROJECT_ROOT, load_accounts, load_env
from .logutil import get_logger
from .models import UsageRecord
from .storage import add_usage_record

PROVIDER_BASE = {
    "openai": "https://api.openai.com",
    "deepseek": "https://api.deepseek.com",
}


def normalize_base(base: str) -> str:
    """去掉结尾的 /v1，统一由路径拼接（兼容 base_url 带或不带 /v1）。"""
    base = base.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def resolve_target(account, path: str) -> str:
    if account.provider in PROVIDER_BASE:
        base = PROVIDER_BASE[account.provider]
    else:
        base = normalize_base(account.base_url or "")
    return base + path


def extract_usage(data: dict) -> dict:
    """从响应 usage 中提取：输入 / 输出 / 命中缓存 / 未命中缓存。

    兼容 DeepSeek 风格（prompt_cache_hit_tokens / prompt_cache_miss_tokens）
    与 OpenAI 风格（prompt_tokens_details.cached_tokens）。
    """
    usage = data.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    if not hit:
        details = usage.get("prompt_tokens_details") or {}
        hit = int(details.get("cached_tokens") or 0)
    miss = max(prompt - hit, 0)
    return {"prompt": prompt, "completion": completion, "hit": hit, "miss": miss}


def estimate_cost(pricing: dict | None, usage: dict) -> float | None:
    """按账户配置的单价（每百万 Token）估算费用；未配置则返回 None。"""
    if not pricing:
        return None
    p_input = float(pricing.get("input") or 0)
    p_hit = float(pricing.get("input_cache_hit") or p_input)
    p_output = float(pricing.get("output") or 0)
    return round(
        (usage["miss"] * p_input + usage["hit"] * p_hit + usage["completion"] * p_output) / 1_000_000,
        6,
    )


logger = get_logger("proxy")


class ProxyHandler(BaseHTTPRequestHandler):
    accounts: list = []
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if urlparse(self.path).path == "/__mb_health":
            self._send_json(200, {"service": "modelbalance-proxy", "ok": True})
            return
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method: str):
        path = urlparse(self.path).path
        account = self._match_account(self.headers.get("Authorization", ""))
        if account is None:
            self._send_json(401, {"error": "未识别的 API Key，请先在 config.json / .env 配置"})
            return
        body = self._read_body() if method == "POST" else None
        target = resolve_target(account, path)
        req = urlrequest.Request(
            target,
            data=body,
            method=method,
            headers=self._forward_headers(),
        )
        try:
            with urlrequest.urlopen(req, timeout=120) as resp:
                status = resp.status
                ctype = resp.headers.get("Content-Type", "application/json")
                if "text/event-stream" in ctype:
                    self._forward_stream(account, body, resp, status, ctype)
                else:
                    payload = resp.read()
                    self._record_if_usage(account, body, payload, ctype)
                    self._send_bytes(status, ctype, payload)
        except HTTPError as exc:
            payload = exc.read()
            status = exc.code
            ctype = exc.headers.get("Content-Type", "application/json") if exc.headers else "application/json"
            self._record_if_usage(account, body, payload, ctype)
            self._send_bytes(status, ctype, payload)
        except URLError as exc:
            self._send_json(502, {"error": f"上游请求失败: {exc}"})

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _forward_headers(self) -> dict:
        headers = {}
        for key in ("Authorization", "Content-Type", "Accept"):
            value = self.headers.get(key)
            if value:
                headers[key] = value
        return headers

    def _match_account(self, auth: str):
        token = auth.removeprefix("Bearer ").strip() if auth else ""
        if not token:
            return None
        for acc in self.accounts:
            if token == acc.api_key:
                return acc
        return None

    def _record_if_usage(self, account, body: bytes | None, payload: bytes, ctype: str) -> None:
        if not body:
            return
        try:
            req_data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if "text/event-stream" in ctype:
            usage = self._usage_from_stream(payload)
        else:
            try:
                usage = extract_usage(json.loads(payload.decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                return
        if not usage or (usage["prompt"] == 0 and usage["completion"] == 0):
            return
        pricing = (account.extra or {}).get("pricing")
        add_usage_record(
            UsageRecord(
                account=account.name,
                model=req_data.get("model") or "",
                prompt_tokens=usage["prompt"],
                completion_tokens=usage["completion"],
                prompt_cache_hit_tokens=usage["hit"],
                prompt_cache_miss_tokens=usage["miss"],
                cost=estimate_cost(pricing, usage),
                note="proxy",
            )
        )

    def _forward_stream(self, account, body, upstream, status: int, ctype: str) -> None:
        """流式响应：边收边转发给客户端，同时缓冲以解析 usage。"""
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Connection", "close")
        self.end_headers()
        buf = b""
        try:
            while True:
                chunk = upstream.read(8192)
                if not chunk:
                    break
                buf += chunk
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            self._record_if_usage(account, body, buf, ctype)

    def _send_bytes(self, status: int, ctype: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def _usage_from_stream(payload: bytes) -> dict | None:
        """从 SSE 流中提取最后携带 usage 的块。"""
        usage = None
        for part in payload.decode("utf-8", errors="replace").split("\n\n"):
            for line in part.splitlines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    data = json.loads(chunk)
                except ValueError:
                    continue
                if data.get("usage"):
                    usage = extract_usage(data)
        return usage

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def _port_in_use(port: int = 8001) -> bool:
    """端口被监听但健康检查失败（可能是其他程序占用）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return False


def proxy_is_running(port: int = 8001) -> bool:
    """检测端口上是否运行着本应用的用量代理（含健康检查，避免误判其他程序）。"""
    if not _port_in_use(port):
        return False
    try:
        with urlrequest.urlopen(f"http://127.0.0.1:{port}/__mb_health", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("service") == "modelbalance-proxy"
    except (URLError, OSError, ValueError):
        return False


def ensure_proxy(port: int = 8001, quiet: bool = False) -> bool:
    """确保用量代理在运行；未运行则后台自动拉起（无窗口）。"""
    if proxy_is_running(port):
        if not quiet:
            print(f"用量代理已在运行: http://127.0.0.1:{port}")
        return True
    if _port_in_use(port):
        if not quiet:
            print(f"端口 {port} 被其他程序占用，未启动用量代理")
        logger.warning("端口 %s 被其他程序占用，未启动用量代理", port)
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if getattr(sys, "frozen", False):
        subprocess.Popen(
            [str(Path(sys.executable)), "--proxy"],
            cwd=str(PROJECT_ROOT),
            creationflags=flags,
        )
    else:
        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        target = pyw if pyw.exists() else exe
        subprocess.Popen(
            [str(target), str(PROJECT_ROOT / "run.py"), "proxy", "--port", str(port)],
            cwd=str(PROJECT_ROOT),
            creationflags=flags,
        )
    if not quiet:
        print(f"已自动启动用量代理: http://127.0.0.1:{port}")
    return True


def run_proxy(host: str = "127.0.0.1", port: int = 8001) -> int:
    load_env()
    accounts = load_accounts()
    if not accounts:
        print("没有配置任何账户，请先编辑 config.json")
        return 1
    ProxyHandler.accounts = accounts
    server = ThreadingHTTPServer((host, port), ProxyHandler)
    logger.info("用量记录代理已启动: http://%s:%s", host, port)
    print(f"用量记录代理已启动: http://{host}:{port}")
    print(f"使用方法：把客户端的 base_url 改为 http://{host}:{port}/v1，API Key 保持原样")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()
        logger.info("用量记录代理已停止")
    return 0