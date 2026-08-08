"""桌面应用（Tkinter，纯标准库）。运行：python run.py app 或双击 启动仪表盘.bat"""
from __future__ import annotations

import os
import queue
import subprocess
from http.server import ThreadingHTTPServer
import sys
import threading
import time
from urllib import request as urlrequest
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from . import __version__
from .codex_usage import sync_codex_usage_to_db
from .config import PROJECT_ROOT, load_accounts, load_env, load_settings, save_setting
from .fetcher import fetch_all
from .lan_sync import LanSyncHandler, get_lan_ip, get_sync_token
from .logutil import get_logger
from .notify import show_system_toast
from .proxy import proxy_is_running
from .storage import (
    add_notification,
    add_snapshot,
    list_notifications,
    list_usage_records,
    mark_all_notifications_read,
    mark_notification_read,
    snapshot_history,
    unread_notification_count,
    usage_breakdown,
    usage_daily,
    usage_totals,
)
from .updater import (
    check_for_update,
    cleanup_updates,
    download_asset,
    fmt_size,
    stage_update,
)

BG = "#0f172a"
GRID = "#475569"
TEXT = "#f8fafc"
DAY_TEXT = "#94a3b8"
BAR_COLOR_COST = "#f87171"
BAR_COLOR_TOKEN = "#4ade80"
PIE_COLORS = {"cache_hit": "#4ade80", "cache_miss": "#60a5fa", "output": "#fb923c"}
TREND_COLORS = ["#38bdf8", "#fbbf24", "#a78bfa", "#34d399", "#fb7185", "#22d3ee"]
FONT_VAL = ("Microsoft YaHei", 10)
FONT_DAY = ("Microsoft YaHei", 10)
FONT_TIP = ("Microsoft YaHei", 10)
SNAPSHOT_INTERVAL_SEC = 1800   # 快照保存最小间隔（秒）
CODEX_SYNC_INTERVAL_SEC = 30   # Codex 用量自动采集间隔（秒）
logger = get_logger("app")


def fmt_money(value) -> str:
    return "-" if value is None else f"{value:.4f}"


def _canvas_size(canvas, fallback_w: int, fallback_h: int) -> tuple[int, int]:
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    return (w if w > 50 else fallback_w, h if h > 50 else fallback_h)


def _notify_type_label(type_: str) -> str:
    return {"low_balance": "低余额", "update_available": "新版本"}.get(type_, type_)


class BalanceApp:
    def __init__(self, root: tk.Tk, interval: int = 30, save: bool = True):
        self.root = root
        self.interval = max(5, interval)
        self.save = save
        self._q: queue.Queue = queue.Queue()
        self._fetching = False
        self._auto_scheduled = False
        self._bar_meta: dict = {}
        self._last_snapshot: dict = {}
        self._proxy_pid: int | None = None
        self._codex_sync_lock = threading.Lock()
        self._notify_windows: list[tk.Toplevel] = []

        root.title(f"模型余额仪表盘 v{__version__}")
        root.geometry("1220x900")
        root.minsize(980, 760)

        # 顶部控制栏
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="立即刷新", command=self.refresh_now).pack(side="left")
        ttk.Button(bar, text="检查更新", command=self.manual_check_update).pack(side="left", padx=(8, 0))
        ttk.Label(bar, text=f"版本 v{__version__}").pack(side="left", padx=(8, 0))
        ttk.Label(bar, text="刷新间隔(秒):").pack(side="left", padx=(16, 4))
        self.interval_var = tk.StringVar(value=str(self.interval))
        ttk.Entry(bar, textvariable=self.interval_var, width=6).pack(side="left")
        self.save_var = tk.BooleanVar(value=self.save)
        ttk.Checkbutton(bar, text="保存余额快照", variable=self.save_var).pack(side="left", padx=12)
        ttk.Label(bar, text="低余额阈值(¥):").pack(side="left", padx=(12, 4))
        self.alert_threshold = load_settings()["alert_threshold"]
        self.alert_entry_var = tk.StringVar(value=str(self.alert_threshold))
        ttk.Entry(bar, textvariable=self.alert_entry_var, width=6).pack(side="left")
        self.include_codex = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="含Codex用量", variable=self.include_codex).pack(side="left", padx=8)
        self.lan_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="局域网同步", variable=self.lan_sync_var, command=self._toggle_lan_sync).pack(side="left", padx=8)
        self.lan_info_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.lan_info_var).pack(side="left", padx=(4, 4))
        self._lan_ip = ""
        self._lan_port = 8002
        self._lan_token = ""
        ttk.Button(bar, text="复制地址", width=8, command=self._copy_lan_url).pack(side="left", padx=(0, 2))
        ttk.Button(bar, text="复制IP", width=7, command=self._copy_lan_ip).pack(side="left", padx=(0, 2))
        ttk.Button(bar, text="复制令牌", width=8, command=self._copy_lan_token).pack(side="left", padx=(0, 8))
        self.msg_button = ttk.Button(bar, text="消息", width=8, command=self.open_notifications)
        self.msg_button.pack(side="left", padx=(0, 8))
        self._update_msg_button()
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(bar, textvariable=self.status_var).pack(side="right")
        self.proxy_var = tk.StringVar(value="用量代理: 检查中…")
        ttk.Label(bar, textvariable=self.proxy_var).pack(side="right", padx=(0, 12))
        self.update_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.update_var).pack(side="right", padx=(0, 12))

        # 余额表
        ttk.Label(root, text="账户余额（实时查询）", padding=(8, 4)).pack(anchor="w")
        bal_cols = ("account", "provider", "currency", "available", "used", "total", "status")
        self.bal_tree = ttk.Treeview(root, columns=bal_cols, show="headings", height=5)
        bal_head = {
            "account": "账户", "provider": "提供商", "currency": "币种",
            "available": "可用金额", "used": "已用金额", "total": "总额", "status": "状态",
        }
        bal_width = {
            "account": 170, "provider": 110, "currency": 60,
            "available": 100, "used": 100, "total": 100, "status": 200,
        }
        for c in bal_cols:
            self.bal_tree.heading(c, text=bal_head[c])
            self.bal_tree.column(c, width=bal_width[c], anchor="center")
        self.bal_tree.pack(fill="x", padx=8)
        self.alert_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.alert_var, padding=(8, 2), foreground="#f87171").pack(anchor="w")

        # 用量区
        ttk.Label(root, text="Token 用量记录（近 30 天）", padding=(8, 6)).pack(anchor="w")
        self.usage_summary_var = tk.StringVar(value="-")
        ttk.Label(root, textvariable=self.usage_summary_var, padding=(8, 0)).pack(anchor="w")
        self.codex_sync_var = tk.StringVar(value="用量采集: 待同步")
        ttk.Label(root, textvariable=self.codex_sync_var, padding=(8, 0), foreground="#94a3b8").pack(anchor="w")
        ttk.Label(
            root,
            text="注：Token 用量来自 Codex 本地会话自动采集（非官方接口数据），与官网可能不一致",
            padding=(8, 0),
            foreground="#94a3b8",
        ).pack(anchor="w")
        use_cols = ("time", "account", "model", "tokens", "cost")
        self.usage_tree = ttk.Treeview(root, columns=use_cols, show="headings", height=4)
        use_head = {"time": "时间", "account": "账户", "model": "模型", "tokens": "Token", "cost": "费用"}
        for c in use_cols:
            self.usage_tree.heading(c, text=use_head[c])
            self.usage_tree.column(c, width=170 if c in ("time", "model") else 110, anchor="center")
        self.usage_tree.pack(fill="x", padx=8)

        # 图表区
        charts = ttk.Frame(root)
        charts.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.cost_frame = ttk.Frame(charts)
        self.cost_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(self.cost_frame, text="每日消费金额（近 14 天，悬停柱子看数值）", padding=(4, 2)).pack(anchor="w")
        self.cost_canvas = tk.Canvas(self.cost_frame, width=420, height=170, bg=BG, highlightthickness=0)
        self.cost_canvas.pack(fill="both", expand=True)

        self.token_frame = ttk.Frame(charts)
        self.token_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(self.token_frame, text="每日 Token 用量（近 14 天，悬停柱子看数值）", padding=(4, 2)).pack(anchor="w")
        self.token_canvas = tk.Canvas(self.token_frame, width=420, height=170, bg=BG, highlightthickness=0)
        self.token_canvas.pack(fill="both", expand=True)

        self.pie_frame = ttk.Frame(charts)
        self.pie_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(self.pie_frame, text="Token 构成（近 30 天）", padding=(4, 2)).pack(anchor="w")
        self.pie_canvas = tk.Canvas(self.pie_frame, width=320, height=170, bg=BG, highlightthickness=0)
        self.pie_canvas.pack(fill="both", expand=True)

        # 余额趋势区
        trend_frame = ttk.Frame(root)
        trend_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        ttk.Label(trend_frame, text="余额趋势（近 30 天，自动保存快照）", padding=(4, 2)).pack(anchor="w")
        self.trend_canvas = tk.Canvas(trend_frame, width=1160, height=150, bg=BG, highlightthickness=0)
        self.trend_canvas.pack(fill="both", expand=True)

        # 用量代理为可选工具（用量统计正式来源为 codex-usage）：不再自动拉起，
        # 需要时手动运行 python run.py proxy；仅显示状态。
        self._proxy_pid = None
        if proxy_is_running(8001):
            self.proxy_var.set("用量代理: 运行中（手动启动）")
        else:
            self.proxy_var.set("用量代理: 未启用")
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        threading.Thread(target=self._auto_check_update, daemon=True).start()

        logger.info("BalanceApp.__init__: 初始化完成，进入定时器")
        self.root.after(200, self._poll_queue)
        self.refresh_now()
        threading.Thread(target=self._codex_sync_loop, daemon=True).start()

    def refresh_now(self):
        if self._fetching:
            return
        try:
            self.interval = max(5, int(self.interval_var.get()))
        except ValueError:
            self.interval = 30
        self.save = self.save_var.get()
        self._fetching = True
        self.status_var.set("刷新中…")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        accounts = load_accounts()
        logger.debug("查询余额开始，账户数=%d", len(accounts))
        results = fetch_all(accounts)
        logger.debug("查询余额完成，结果数=%d", len(results))
        self._q.put(results)

    def _poll_queue(self):
        try:
            while True:
                results = self._q.get_nowait()
                logger.debug("开始渲染界面")
                try:
                    self._render(results)
                except Exception:  # noqa: BLE001
                    logger.exception("渲染失败")
                logger.debug("渲染完成")
                self._fetching = False
                self.status_var.set(f"最后刷新：{datetime.now().strftime('%H:%M:%S')}")
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)
        if not self._fetching and not self._auto_scheduled:
            self._auto_scheduled = True
            self.root.after(self.interval * 1000, self._auto_refresh)

    def _auto_refresh(self):
        self._auto_scheduled = False
        self.refresh_now()

    def _codex_sync_loop(self):
        """后台定时采集 Codex 用量：启动即同步一次，之后每 CODEX_SYNC_INTERVAL_SEC 秒一次。"""
        self._codex_sync_once()
        while True:
            time.sleep(CODEX_SYNC_INTERVAL_SEC)
            self._codex_sync_once()

    def _codex_sync_once(self):
        """执行一次增量采集；有新记录时刷新用量区显示。"""
        if not self._codex_sync_lock.acquire(blocking=False):
            return
        try:
            added = sync_codex_usage_to_db()
        except Exception:  # noqa: BLE001 - 后台采集失败不影响主界面
            logger.exception("自动采集 Codex 用量失败")
            self.root.after(0, lambda: self.codex_sync_var.set("用量采集: 失败"))
            return
        finally:
            self._codex_sync_lock.release()
        if added:
            logger.info("自动采集 Codex 用量新增 %d 条", added)
            self.root.after(0, self._render_usage)
        self.root.after(
            0,
            lambda: self.codex_sync_var.set(
                f"用量采集: {datetime.now().strftime('%H:%M:%S')}"
                + (f"（新增 {added} 条）" if added else "（已最新）")
            ),
        )

    def _current_threshold(self) -> float:
        """读取用户设置的阈值；变更时写回 config.json。"""
        try:
            threshold = max(0.0, float(self.alert_entry_var.get()))
        except ValueError:
            threshold = self.alert_threshold
        if abs(threshold - self.alert_threshold) > 1e-9:
            self.alert_threshold = threshold
            save_setting("alert_threshold", threshold)
        return threshold

    def _maybe_save_snapshot(self, balance):
        """快照限频保存（默认至少间隔 30 分钟），避免刷屏。"""
        last = self._last_snapshot.get(balance.account)
        now = datetime.now()
        if last is None or (now - last).total_seconds() >= SNAPSHOT_INTERVAL_SEC:
            add_snapshot(balance)
            self._last_snapshot[balance.account] = now

    # ---------- 消息中心 ----------

    def _notify_low_balance(self, balance, threshold: float) -> None:
        """低余额：写入消息中心并弹系统通知（同账户同日去重）。"""
        key = f"low_balance:{balance.account}:{datetime.now():%Y-%m-%d}"
        title = "低余额提醒"
        body = (
            f"{balance.account} 可用余额 {balance.available:.4f} "
            f"{balance.currency}，低于阈值 {threshold:.2f}。"
        )
        try:
            nid = add_notification("low_balance", title, body, dedupe_key=key)
        except Exception:  # noqa: BLE001
            logger.exception("写入低余额消息失败")
            return
        if nid:
            show_system_toast(
                title,
                f"{balance.account} 可用余额低于 {threshold:.2f} {balance.currency}",
            )
            self._refresh_notify_windows()

    def _notify_update_available(self, info: dict) -> None:
        """发现新版本：写入消息中心并弹系统通知（按版本号去重）。"""
        title = f"发现新版本 v{info['tag_name']}"
        body = info.get("body") or "有新版本可用，可在应用内查看并更新。"
        try:
            nid = add_notification(
                "update_available",
                title,
                body,
                dedupe_key=f"update_available:{info['tag_name']}",
            )
        except Exception:  # noqa: BLE001
            logger.exception("写入新版本消息失败")
            return
        if nid:
            show_system_toast(title, "模型余额有新版本可用。")
            self._refresh_notify_windows()

    def _update_msg_button(self) -> None:
        try:
            count = unread_notification_count()
        except Exception:  # noqa: BLE001
            count = 0
        self.msg_button.config(text=f"消息({count})" if count else "消息")

    def open_notifications(self) -> None:
        """打开消息中心窗口。"""
        win = tk.Toplevel(self.root)
        win.title("消息中心")
        win.geometry("620x460")
        win.minsize(520, 340)
        win.transient(self.root)
        self._notify_windows.append(win)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_notify_window(win))

        top = ttk.Frame(win, padding=(8, 8))
        top.pack(fill="x")
        ttk.Label(top, text="系统通知消息").pack(side="left")
        ttk.Button(
            top, text="全部已读", command=self._mark_all_notifications_read
        ).pack(side="right")
        ttk.Button(
            top, text="刷新", command=lambda: self._reload_notifications(win)
        ).pack(side="right", padx=(0, 6))

        cols = ("id", "time", "type", "title", "body")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
        heads = {
            "time": "时间",
            "type": "类型",
            "title": "标题",
            "body": "内容",
        }
        widths = {"id": 40, "time": 130, "type": 70, "title": 150, "body": 220}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor="w", stretch=c == "body")
        tree.column("id", width=0, stretch=False)
        tree.tag_configure("unread", font=("Microsoft YaHei", 10, "bold"))
        tree.tag_configure("read", foreground="#94a3b8")
        tree.bind("<Double-1>", lambda e: self._on_notify_open(win, tree, e))
        tree.bind("<ButtonRelease-1>", lambda e: self._on_notify_click(win, tree, e))
        tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        win.tree = tree
        self._reload_notifications(win)

    def _close_notify_window(self, win: tk.Toplevel) -> None:
        if win in self._notify_windows:
            self._notify_windows.remove(win)
        win.destroy()

    def _reload_notifications(self, win: tk.Toplevel) -> None:
        tree = getattr(win, "tree", None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        try:
            items = list_notifications()
        except Exception:  # noqa: BLE001
            logger.exception("读取消息失败")
            return
        for n in items:
            tags = ("unread",) if not n["read"] else ("read",)
            tree.insert(
                "",
                "end",
                values=(
                    n["id"],
                    n["created_at"],
                    _notify_type_label(n["type"]),
                    n["title"],
                    n["body"],
                ),
                tags=tags,
            )

    def _on_notify_click(self, win: tk.Toplevel, tree: ttk.Treeview, event) -> None:
        """单击标记已读。"""
        sel = tree.selection()
        if not sel:
            return
        values = tree.item(sel[0], "values")
        if not values:
            return
        try:
            mark_notification_read(int(values[0]))
        except Exception:  # noqa: BLE001
            return
        self._reload_notifications(win)
        self._update_msg_button()

    def _on_notify_open(self, win: tk.Toplevel, tree: ttk.Treeview, event) -> None:
        """双击查看消息详情。"""
        sel = tree.selection()
        if not sel:
            return
        values = tree.item(sel[0], "values")
        if not values:
            return
        try:
            mark_notification_read(int(values[0]))
        except Exception:  # noqa: BLE001
            pass
        self._reload_notifications(win)
        self._update_msg_button()
        messagebox.showinfo(
            "消息详情",
            f"{values[3]}\n\n{values[4]}\n\n时间：{values[1]}",
            parent=win,
        )

    def _mark_all_notifications_read(self) -> None:
        try:
            mark_all_notifications_read()
        except Exception:  # noqa: BLE001
            logger.exception("全部已读失败")
            return
        self._refresh_notify_windows()

    def _refresh_notify_windows(self) -> None:
        """后台线程调用时安全：通过主线程 after 刷新消息窗口与按钮。"""
        self.root.after(0, self._refresh_notify_windows_now)

    def _refresh_notify_windows_now(self) -> None:
        for win in list(self._notify_windows):
            if win.winfo_exists():
                self._reload_notifications(win)
            else:
                self._notify_windows.remove(win)
        self._update_msg_button()

    def _render(self, results):
        for item in self.bal_tree.get_children():
            self.bal_tree.delete(item)
        low_accounts = []
        threshold = self._current_threshold()
        for r in results:
            if r.ok:
                b = r.balance
                self.bal_tree.insert(
                    "",
                    "end",
                    values=(
                        b.account, b.provider, b.currency,
                        fmt_money(b.available), fmt_money(b.used), fmt_money(b.total), "OK",
                    ),
                )
                if self.save:
                    self._maybe_save_snapshot(b)
                if b.available is not None and b.available < threshold:
                    low_accounts.append(f"{b.account} ¥{b.available:.2f}")
                    self._notify_low_balance(b, threshold)

            else:
                self.bal_tree.insert(
                    "", "end",
                    values=(r.account.name, r.account.provider, "-", "-", "-", "-", r.error),
                )
        self.alert_var.set(f"⚠ 低余额提醒: {'、'.join(low_accounts)}" if low_accounts else "")

        self._render_usage()

    def _render_usage(self):
        """刷新 Token 用量表与图表（余额区不变）。"""
        since = datetime.now() - timedelta(days=14)
        exclude = None if self.include_codex.get() else "codex"
        for item in self.usage_tree.get_children():
            self.usage_tree.delete(item)
        totals = usage_totals(since=since, exclude=exclude)
        records = list_usage_records(since=since, exclude=exclude)
        latest_txt = ""
        if records:
            r0 = records[0]
            latest_txt = f" | 最新 {r0['created_at'][11:19]} {r0['model']} {r0['total_tokens']}t"
        self.usage_summary_var.set(
            f"共 {totals['records']} 条记录 / {totals['total_tokens']} tokens / "
            f"费用 {totals['cost']:.4f}{latest_txt}"
        )
        for rec in records[:20]:
            self.usage_tree.insert(
                "", "end",
                values=(rec["created_at"], rec["account"], rec["model"], rec["total_tokens"], fmt_money(rec["cost"])),
            )

        daily = usage_daily(days=14, exclude=exclude)
        breakdown = usage_breakdown(since=since, exclude=exclude)
        trend = snapshot_history(days=30)
        logger.debug("图表数据 daily=%s", daily)
        logger.debug("图表数据 breakdown=%s", breakdown)
        logger.debug("图表数据 trend 条数=%d", len(trend))
        self._draw_bars(self.cost_canvas, daily, "cost", lambda v: f"¥{v:.2f}", BAR_COLOR_COST)
        self._draw_bars(self.token_canvas, daily, "tokens", lambda v: f"{v:,}", BAR_COLOR_TOKEN)
        self._draw_pie(self.pie_canvas, breakdown)
        self._draw_trend(self.trend_canvas, trend)

    # ---------- 图表绘制 ----------

    def _draw_bars(self, canvas, daily, value_key, fmt, color):
        canvas.delete("all")
        w, h = _canvas_size(canvas, 420, 170)
        ml, mr, mt, mb = 58, 10, 20, 32
        pw, ph = w - ml - mr, h - mt - mb
        max_v = max((d[value_key] for d in daily), default=0) or 1
        n = len(daily)
        slot = pw / max(n, 1)
        bar_w = min(slot * 0.62, 38)
        bar_ids = []
        for i, d in enumerate(daily):
            v = d[value_key]
            bh = ph * v / max_v
            x0 = ml + i * slot + (slot - bar_w) / 2
            y0 = mt + ph - bh
            bid = canvas.create_rectangle(x0, y0, x0 + bar_w, mt + ph, fill=color, outline="")
            bar_ids.append(bid)
            if bh > 18:
                canvas.create_text(x0 + bar_w / 2, y0 - 8, text=fmt(v), fill=TEXT, font=FONT_VAL)
            if i % 2 == 0:
                canvas.create_text(x0 + bar_w / 2, mt + ph + 16, text=d["day"][5:], fill=DAY_TEXT, font=FONT_DAY)
        for g in range(5):
            gy = mt + ph - ph * g / 4
            canvas.create_line(ml, gy, ml + pw, gy, fill=GRID, dash=(2, 2))
            canvas.create_text(ml - 6, gy, text=fmt(max_v * g / 4), anchor="e", fill=TEXT, font=FONT_VAL)
        canvas.create_line(ml, mt + ph, ml + pw, mt + ph, fill=TEXT)
        canvas.create_line(ml, mt, ml, mt + ph, fill=TEXT)
        self._bar_meta[canvas] = {
            "daily": daily,
            "value_key": value_key,
            "fmt": fmt,
            "color": color,
            "ml": ml, "mt": mt, "pw": pw, "ph": ph,
            "slot": slot, "bar_w": bar_w, "bar_ids": bar_ids,
            "w": w, "h": h,
        }
        canvas.bind("<Motion>", lambda e, cv=canvas: self._on_bar_hover(e, cv))
        canvas.bind("<Leave>", lambda e, cv=canvas: self._on_bar_leave(cv))

    def _on_bar_hover(self, event, canvas):
        meta = self._bar_meta.get(canvas)
        if not meta:
            return
        x, y = event.x, event.y
        ml, mt, pw, ph, slot = meta["ml"], meta["mt"], meta["pw"], meta["ph"], meta["slot"]
        canvas.delete("bar_hl")
        canvas.delete("bar_tip")
        for bid in meta["bar_ids"]:
            canvas.itemconfigure(bid, outline="")
        if not (ml <= x <= ml + pw and mt <= y <= mt + ph):
            return
        n = len(meta["daily"])
        idx = min(int((x - ml) / slot), n - 1)
        if idx < 0:
            return
        bid = meta["bar_ids"][idx]
        canvas.itemconfigure(bid, outline="#ffffff", width=2)
        d = meta["daily"][idx]
        if meta["value_key"] == "cost":
            line = f"{d['day']}  消费 ¥{d['cost']:.2f}"
        else:
            line = f"{d['day']}  Token {d['tokens']:,}"
        tx = min(x + 14, meta["w"] - 222)
        ty = max(y - 34, 10)
        canvas.create_rectangle(tx, ty, tx + 216, ty + 28, fill="#0b1220", outline="#64748b", tags=("bar_tip",))
        canvas.create_text(tx + 8, ty + 14, anchor="w", text=line, fill="#ffffff", font=FONT_TIP, tags=("bar_tip",))

    def _on_bar_leave(self, canvas):
        canvas.delete("bar_hl")
        canvas.delete("bar_tip")
        meta = self._bar_meta.get(canvas)
        if meta:
            for bid in meta["bar_ids"]:
                canvas.itemconfigure(bid, outline="")

    def _draw_pie(self, canvas, breakdown):
        canvas.delete("all")
        w, h = _canvas_size(canvas, 320, 170)
        cx, cy = w * 0.30, h * 0.48
        r = min(w, h) * 0.36
        items = [
            ("输入(命中缓存)", breakdown["cache_hit"], PIE_COLORS["cache_hit"]),
            ("输入(未命中缓存)", breakdown["cache_miss"], PIE_COLORS["cache_miss"]),
            ("输出", breakdown["output"], PIE_COLORS["output"]),
        ]
        total = sum(v for _, v, _ in items) or 1
        start = 90.0
        for label, v, color in items:
            if v <= 0:
                continue
            extent = -360.0 * v / total
            canvas.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=start, extent=extent, fill=color, outline=BG, width=1,
            )
            start += extent
        lx = w * 0.58
        ly = h * 0.16
        for label, v, color in items:
            pct = 100.0 * v / total
            canvas.create_rectangle(lx, ly, lx + 14, ly + 14, fill=color, outline="")
            canvas.create_text(
                lx + 20, ly + 7, anchor="w",
                text=f"{label}  {pct:.1f}%", fill=TEXT, font=FONT_VAL,
            )
            ly += 28

    def _draw_trend(self, canvas, history):
        canvas.delete("all")
        w, h = _canvas_size(canvas, 1160, 150)
        ml, mr, mt, mb = 58, 10, 20, 30
        pw, ph = w - ml - mr, h - mt - mb
        if not history:
            canvas.create_text(
                w / 2, h / 2, text="暂无余额快照数据（应用会自动保存）",
                fill=DAY_TEXT, font=FONT_DAY,
            )
            return
        by_acct: dict[str, list] = {}
        for rec in history:
            by_acct.setdefault(rec["account"], []).append(rec)
        max_v = max((r["available"] or 0) for r in history) or 1
        times = [datetime.fromisoformat(r["created_at"]) for r in history]
        t0, t1 = min(times), max(times)
        span = max((t1 - t0).total_seconds(), 1)
        for g in range(5):
            gy = mt + ph - ph * g / 4
            canvas.create_line(ml, gy, ml + pw, gy, fill=GRID, dash=(2, 2))
            canvas.create_text(ml - 6, gy, text=f"¥{max_v * g / 4:.2f}", anchor="e", fill=TEXT, font=FONT_DAY)
        for idx, (acct, pts) in enumerate(by_acct.items()):
            color = TREND_COLORS[idx % len(TREND_COLORS)]
            coords = []
            for r in pts:
                t = datetime.fromisoformat(r["created_at"])
                x = ml + pw * ((t - t0).total_seconds() / span)
                y = mt + ph - ph * (r["available"] or 0) / max_v
                coords.append((x, y))
            for i in range(1, len(coords)):
                canvas.create_line(*coords[i - 1], *coords[i], fill=color, width=2)
            for x, y in coords:
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline="")
            lx = ml + 10 + (idx % 2) * (pw // 2)
            ly = mt + 12 + (idx // 2) * 18
            canvas.create_rectangle(lx, ly, lx + 10, ly + 10, fill=color, outline="")
            canvas.create_text(lx + 16, ly + 5, anchor="w", text=acct, fill=TEXT, font=FONT_DAY)
        canvas.create_line(ml, mt + ph, ml + pw, mt + ph, fill=TEXT)
        canvas.create_line(ml, mt, ml, mt + ph, fill=TEXT)
        canvas.create_text(ml, mt + ph + 14, anchor="w", text=t0.strftime("%m-%d"), fill=DAY_TEXT, font=FONT_DAY)
        canvas.create_text(ml + pw, mt + ph + 14, anchor="e", text=t1.strftime("%m-%d"), fill=DAY_TEXT, font=FONT_DAY)

    # ---------- 更新 ----------

    def _auto_check_update(self):
        try:
            info = check_for_update(__version__)
        except Exception:  # noqa: BLE001 网络异常不误报"已是最新"
            self.root.after(0, lambda: self.update_var.set("更新: 检查失败"))
            return
        if info:
            self._notify_update_available(info)
            self.root.after(0, lambda: self._prompt_update(info))
        else:
            self.root.after(0, lambda: self.update_var.set("更新: 已是最新"))

    def manual_check_update(self):
        self.update_var.set("更新: 检查中…")
        threading.Thread(target=self._manual_check_worker, daemon=True).start()

    def _manual_check_worker(self):
        try:
            info = check_for_update(__version__)
        except Exception:  # noqa: BLE001
            self.root.after(0, lambda: self.update_var.set("更新: 检查失败"))
            return
        if info:
            self._notify_update_available(info)
            self.root.after(0, lambda: self._prompt_update(info))
        else:
            self.root.after(0, lambda: self.update_var.set("更新: 已是最新"))

    def _prompt_update(self, info):
        self.update_var.set(f"更新: 发现 v{info['tag_name']}")
        size = fmt_size(info["asset_size"])
        body = info["body"] or "（发布者未填写更新说明）"
        msg = (
            f"发现新版本 v{info['tag_name']}\n"
            f"当前版本: v{__version__}\n"
            f"更新包大小: {size}\n\n"
            f"本次更新内容:\n{body}\n\n"
            "是否立即下载并更新？"
        )
        if messagebox.askyesno("发现更新", msg, parent=self.root, icon="info"):
            self._download_update(info)

    def _download_update(self, info):
        win = tk.Toplevel(self.root)
        win.title("正在更新")
        win.geometry("380x130")
        win.transient(self.root)
        ttk.Label(win, text=f"正在下载 {info['asset_name']}（{fmt_size(info['asset_size'])}）…").pack(pady=(14, 6))
        self._dl_bar = ttk.Progressbar(win, maximum=100, length=320)
        self._dl_bar.pack(pady=4)
        self._dl_label = ttk.Label(win, text="0%")
        self._dl_label.pack()
        self._dl_q: queue.Queue = queue.Queue()
        self._dl_win = win
        threading.Thread(target=self._dl_worker, args=(info,), daemon=True).start()
        self.root.after(100, self._poll_download)

    def _dl_worker(self, info):
        try:
            dest = PROJECT_ROOT / "data" / "updates" / info["asset_name"]
            download_asset(info["asset_url"], dest, progress_cb=lambda d, t: self._dl_q.put(("progress", d, t)))
            self._dl_q.put(("done", dest))
        except Exception as exc:  # noqa: BLE001
            logger.error("更新包下载失败: %s", exc)
            self._dl_q.put(("error", str(exc)))

    def _poll_download(self):
        try:
            while True:
                msg = self._dl_q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, done, total = msg
                    pct = int(done * 100 / total) if total else 0
                    self._dl_bar["value"] = pct
                    self._dl_label.config(text=f"{pct}%  {fmt_size(done)}/{fmt_size(total)}")
                elif kind == "done":
                    self._dl_win.destroy()
                    self._apply_and_restart(msg[1])
                    return
                elif kind == "error":
                    self._dl_win.destroy()
                    messagebox.showerror("更新失败", f"下载失败: {msg[1]}", parent=self.root)
                    self.update_var.set("更新: 下载失败")
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll_download)

    def _apply_and_restart(self, asset_path):
        self.update_var.set("更新: 准备安装…")
        try:
            if getattr(sys, "frozen", False):
                self._apply_exe_update(Path(asset_path))
            else:
                stage_update(Path(asset_path))
                cleanup_updates()
                self._spawn_dev_updater()
        except Exception as exc:  # noqa: BLE001
            logger.error("准备更新失败: %s", exc)
            messagebox.showerror("更新失败", f"准备更新失败: {exc}", parent=self.root)
            self.update_var.set("更新: 准备失败")
            return
        if self._proxy_pid:
            self._stop_spawned_proxy()
        messagebox.showinfo("更新", "更新已准备好，应用即将重启完成安装。", parent=self.root)
        self.root.destroy()

    def _on_close(self):
        if self._proxy_pid:
            self._stop_spawned_proxy()
        if self.lan_sync_var.get():
            self._stop_lan_sync()
        self.root.destroy()

    def _toggle_lan_sync(self):
        if self.lan_sync_var.get():
            self._start_lan_sync()
        else:
            self._stop_lan_sync()

    def _start_lan_sync(self):
        try:
            self.lan_server = ThreadingHTTPServer(("0.0.0.0", 8002), LanSyncHandler)
        except OSError as exc:
            self.lan_sync_var.set(False)
            self.lan_info_var.set(f"启动失败（8002 被占用?）: {exc}")
            return
        threading.Thread(target=self.lan_server.serve_forever, daemon=True).start()
        ip = get_lan_ip()
        token = get_sync_token()
        self._lan_ip = ip
        self._lan_port = 8002
        self._lan_token = token
        self.lan_info_var.set(f"IP: {ip}:8002 | 令牌: {token[:8]}…")

    def _stop_lan_sync(self):
        if getattr(self, "lan_server", None):
            try:
                self.lan_server.shutdown()
                self.lan_server.server_close()
            except Exception:  # noqa: BLE001
                pass
            self.lan_server = None
        self._lan_ip = ""
        self._lan_token = ""
        self.lan_info_var.set("")

    def _copy_to_clipboard(self, text: str, label: str):
        """复制文本到剪贴板，并在状态栏提示。"""
        if not text:
            self.status_var.set(f"{label}: 未启动局域网同步")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status_var.set(f"{label}: 已复制 {text}")

    def _copy_lan_url(self):
        """复制手机端填写的完整地址 http://IP:端口。"""
        if not self._lan_ip:
            self.status_var.set("复制地址: 未启动局域网同步")
            return
        self._copy_to_clipboard(f"http://{self._lan_ip}:{self._lan_port}", "复制地址")

    def _copy_lan_ip(self):
        """复制局域网 IP。"""
        self._copy_to_clipboard(self._lan_ip, "复制IP")

    def _copy_lan_token(self):
        """复制完整同步令牌。"""
        self._copy_to_clipboard(self._lan_token, "复制令牌")

    def _stop_spawned_proxy(self):
        """优雅关闭自己拉起的代理子进程（避免占用文件导致 PyInstaller 清理失败）。"""
        try:
            urlrequest.urlopen("http://127.0.0.1:8001/__mb_shutdown", timeout=3)
        except Exception:  # noqa: BLE001
            pass
        deadline = time.time() + 3
        while time.time() < deadline:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {self._proxy_pid}"],
                capture_output=True, text=True,
            )
            if str(self._proxy_pid) not in r.stdout:
                break
            time.sleep(0.3)
        else:
            subprocess.run(
                ["taskkill", "/PID", str(self._proxy_pid), "/F"],
                capture_output=True,
            )
        self._proxy_pid = None

    def _spawn_dev_updater(self):
        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        target = pyw if pyw.exists() else exe
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [str(target), str(PROJECT_ROOT / "apply_staged.py"), str(os.getpid())],
            cwd=str(PROJECT_ROOT),
            creationflags=flags,
        )

    def _apply_exe_update(self, new_exe: Path):
        """冻结（exe）模式：生成 cmd 辅助脚本，等待本进程退出后替换 exe 并重启。"""
        target_exe = Path(sys.executable)
        bat = PROJECT_ROOT / "data" / "update_apply.bat"
        bat.parent.mkdir(parents=True, exist_ok=True)
        bat.write_text(
            "@echo off\r\n"
            'set "MB_NEW=%MB_NEW_EXE%"\r\n'
            'set "MB_TGT=%MB_TARGET_EXE%"\r\n'
            'set "MB_PID=%MB_APP_PID%"\r\n'
            ":loop\r\n"
            'tasklist /FI "PID eq %MB_PID%" | find "%MB_PID%" >nul\r\n'
            "if %errorlevel%==0 (timeout /t 1 /nobreak >nul & goto loop)\r\n"
            'move /y "%MB_NEW%" "%MB_TGT%"\r\n'
            'start "" "%MB_TGT%"\r\n'
            'del "%~f0"\r\n',
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["MB_NEW_EXE"] = str(new_exe)
        env["MB_TARGET_EXE"] = str(target_exe)
        env["MB_APP_PID"] = str(os.getpid())
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat)],
            env=env, cwd=str(PROJECT_ROOT), creationflags=flags,
        )


def run_app(interval: int = 30, save: bool = True) -> int:
    load_env()
    logger.info("run_app: 准备创建 Tk 窗口")
    root = tk.Tk()
    logger.info("run_app: Tk 窗口已创建")
    BalanceApp(root, interval=interval, save=save)
    logger.info("run_app: BalanceApp 初始化完成")
    root.mainloop()
    logger.info("run_app: 主循环退出")
    return 0
