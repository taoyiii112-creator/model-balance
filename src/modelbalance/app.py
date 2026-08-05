"""桌面应用（Tkinter，纯标准库）。运行：python run.py app 或双击 启动仪表盘.bat"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

from .config import load_accounts, load_env
from .fetcher import fetch_all
from .storage import add_snapshot, list_usage_records, usage_totals


def fmt_money(value) -> str:
    return "-" if value is None else f"{value:.4f}"


class BalanceApp:
    def __init__(self, root: tk.Tk, interval: int = 30, save: bool = False):
        self.root = root
        self.interval = max(5, interval)
        self.save = save
        self._q: queue.Queue = queue.Queue()
        self._fetching = False
        self._auto_scheduled = False

        root.title("模型余额仪表盘")
        root.geometry("880x640")
        root.minsize(720, 520)

        # 顶部控制栏
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="立即刷新", command=self.refresh_now).pack(side="left")
        ttk.Label(bar, text="刷新间隔(秒):").pack(side="left", padx=(16, 4))
        self.interval_var = tk.StringVar(value=str(self.interval))
        ttk.Entry(bar, textvariable=self.interval_var, width=6).pack(side="left")
        self.save_var = tk.BooleanVar(value=self.save)
        ttk.Checkbutton(bar, text="保存余额快照", variable=self.save_var).pack(side="left", padx=12)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(bar, textvariable=self.status_var).pack(side="right")

        # 余额表
        ttk.Label(root, text="账户余额（实时查询）", padding=(8, 4)).pack(anchor="w")
        bal_cols = ("account", "provider", "currency", "available", "used", "total", "status")
        self.bal_tree = ttk.Treeview(root, columns=bal_cols, show="headings", height=8)
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

        # 用量区
        ttk.Label(root, text="Token 用量（近 30 天）", padding=(8, 8)).pack(anchor="w")
        self.usage_summary_var = tk.StringVar(value="-")
        ttk.Label(root, textvariable=self.usage_summary_var, padding=(8, 0)).pack(anchor="w")
        use_cols = ("time", "account", "model", "tokens", "cost")
        self.usage_tree = ttk.Treeview(root, columns=use_cols, show="headings", height=8)
        use_head = {"time": "时间", "account": "账户", "model": "模型", "tokens": "Token", "cost": "费用"}
        for c in use_cols:
            self.usage_tree.heading(c, text=use_head[c])
            self.usage_tree.column(c, width=170 if c in ("time", "model") else 110, anchor="center")
        self.usage_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.root.after(200, self._poll_queue)
        self.refresh_now()

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
        results = fetch_all(load_accounts())
        self._q.put(results)

    def _poll_queue(self):
        try:
            while True:
                results = self._q.get_nowait()
                self._render(results)
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

    def _render(self, results):
        for item in self.bal_tree.get_children():
            self.bal_tree.delete(item)
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
                    add_snapshot(b)
            else:
                self.bal_tree.insert(
                    "", "end",
                    values=(r.account.name, r.account.provider, "-", "-", "-", "-", r.error),
                )

        since = datetime.now() - timedelta(days=30)
        for item in self.usage_tree.get_children():
            self.usage_tree.delete(item)
        totals = usage_totals(since=since)
        self.usage_summary_var.set(
            f"共 {totals['records']} 条记录 / {totals['total_tokens']} tokens / 费用 {totals['cost']:.4f}"
        )
        for rec in list_usage_records(since=since)[:20]:
            self.usage_tree.insert(
                "", "end",
                values=(rec["created_at"], rec["account"], rec["model"], rec["total_tokens"], fmt_money(rec["cost"])),
            )


def run_app(interval: int = 30, save: bool = False) -> int:
    load_env()
    root = tk.Tk()
    BalanceApp(root, interval=interval, save=save)
    root.mainloop()
    return 0