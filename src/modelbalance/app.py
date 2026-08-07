"""桌面应用（Tkinter，纯标准库）。运行：python run.py app 或双击 启动仪表盘.bat"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

from .config import load_accounts, load_env
from .fetcher import fetch_all
from .storage import (
    add_snapshot,
    list_usage_records,
    usage_breakdown,
    usage_daily,
    usage_totals,
)

BG = "#1e293b"
GRID = "#334155"
TEXT = "#e2e8f0"
BAR_COLOR_COST = "#f59e0b"
BAR_COLOR_TOKEN = "#38bdf8"
PIE_COLORS = {"cache_hit": "#22c55e", "cache_miss": "#3b82f6", "output": "#f97316"}


def fmt_money(value) -> str:
    return "-" if value is None else f"{value:.4f}"


def _canvas_size(canvas, fallback_w: int, fallback_h: int) -> tuple[int, int]:
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    return (w if w > 50 else fallback_w, h if h > 50 else fallback_h)


class BalanceApp:
    def __init__(self, root: tk.Tk, interval: int = 30, save: bool = False):
        self.root = root
        self.interval = max(5, interval)
        self.save = save
        self._q: queue.Queue = queue.Queue()
        self._fetching = False
        self._auto_scheduled = False

        root.title("模型余额仪表盘")
        root.geometry("1220x920")
        root.minsize(1000, 780)

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
        self.bal_tree = ttk.Treeview(root, columns=bal_cols, show="headings", height=6)
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
        ttk.Label(root, text="Token 用量记录（近 30 天）", padding=(8, 6)).pack(anchor="w")
        self.usage_summary_var = tk.StringVar(value="-")
        ttk.Label(root, textvariable=self.usage_summary_var, padding=(8, 0)).pack(anchor="w")
        use_cols = ("time", "account", "model", "tokens", "cost")
        self.usage_tree = ttk.Treeview(root, columns=use_cols, show="headings", height=5)
        use_head = {"time": "时间", "account": "账户", "model": "模型", "tokens": "Token", "cost": "费用"}
        for c in use_cols:
            self.usage_tree.heading(c, text=use_head[c])
            self.usage_tree.column(c, width=170 if c in ("time", "model") else 110, anchor="center")
        self.usage_tree.pack(fill="x", padx=8)

        # 图表区
        charts = ttk.Frame(root)
        charts.pack(fill="both", expand=True, padx=8, pady=(8, 8))

        self.cost_frame = ttk.Frame(charts)
        self.cost_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(self.cost_frame, text="每日消费金额（近 14 天）", padding=(4, 2)).pack(anchor="w")
        self.cost_canvas = tk.Canvas(self.cost_frame, width=420, height=220, bg=BG, highlightthickness=0)
        self.cost_canvas.pack(fill="both", expand=True)

        self.token_frame = ttk.Frame(charts)
        self.token_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(self.token_frame, text="每日 Token 用量（近 14 天）", padding=(4, 2)).pack(anchor="w")
        self.token_canvas = tk.Canvas(self.token_frame, width=420, height=220, bg=BG, highlightthickness=0)
        self.token_canvas.pack(fill="both", expand=True)

        self.pie_frame = ttk.Frame(charts)
        self.pie_frame.pack(side="left", fill="both", expand=True)
        ttk.Label(self.pie_frame, text="Token 构成（近 30 天）", padding=(4, 2)).pack(anchor="w")
        self.pie_canvas = tk.Canvas(self.pie_frame, width=300, height=220, bg=BG, highlightthickness=0)
        self.pie_canvas.pack(fill="both", expand=True)

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
            f"共 {totals['records']} 条记录 / {totals['total_tokens']} tokens / "
            f"费用 {totals['cost']:.4f}"
        )
        for rec in list_usage_records(since=since)[:20]:
            self.usage_tree.insert(
                "", "end",
                values=(rec["created_at"], rec["account"], rec["model"], rec["total_tokens"], fmt_money(rec["cost"])),
            )

        daily = usage_daily(days=14)
        self._draw_bars(self.cost_canvas, daily, "cost", lambda v: f"¥{v:.2f}", BAR_COLOR_COST)
        self._draw_bars(self.token_canvas, daily, "tokens", lambda v: f"{v:,}", BAR_COLOR_TOKEN)
        self._draw_pie(self.pie_canvas, usage_breakdown(since=since))

    # ---------- 图表绘制 ----------

    def _draw_bars(self, canvas, daily, value_key, fmt, color):
        canvas.delete("all")
        w, h = _canvas_size(canvas, 420, 220)
        ml, mr, mt, mb = 52, 8, 16, 26
        pw, ph = w - ml - mr, h - mt - mb
        max_v = max((d[value_key] for d in daily), default=0) or 1
        n = len(daily)
        slot = pw / max(n, 1)
        bar_w = min(slot * 0.6, 34)
        font = ("Microsoft YaHei", 8)
        for i, d in enumerate(daily):
            v = d[value_key]
            bh = ph * v / max_v
            x0 = ml + i * slot + (slot - bar_w) / 2
            y0 = mt + ph - bh
            canvas.create_rectangle(x0, y0, x0 + bar_w, mt + ph, fill=color, outline="")
            if bh > 12:
                canvas.create_text(x0 + bar_w / 2, y0 - 6, text=fmt(v), fill=TEXT, font=font)
            if i % 2 == 0:
                canvas.create_text(x0 + bar_w / 2, mt + ph + 12, text=d["day"][5:], fill=GRID, font=font)
        for g in range(5):
            gy = mt + ph - ph * g / 4
            canvas.create_line(ml, gy, ml + pw, gy, fill=GRID, dash=(2, 2))
            canvas.create_text(ml - 5, gy, text=fmt(max_v * g / 4), anchor="e", fill=TEXT, font=font)
        canvas.create_line(ml, mt + ph, ml + pw, mt + ph, fill=TEXT)
        canvas.create_line(ml, mt, ml, mt + ph, fill=TEXT)

    def _draw_pie(self, canvas, breakdown):
        canvas.delete("all")
        w, h = _canvas_size(canvas, 300, 220)
        cx, cy = w * 0.32, h * 0.48
        r = min(w, h) * 0.36
        items = [
            ("输入(命中缓存)", breakdown["cache_hit"], PIE_COLORS["cache_hit"]),
            ("输入(未命中缓存)", breakdown["cache_miss"], PIE_COLORS["cache_miss"]),
            ("输出", breakdown["output"], PIE_COLORS["output"]),
        ]
        total = sum(v for _, v, _ in items) or 1
        start = 90.0
        font = ("Microsoft YaHei", 8)
        for label, v, color in items:
            if v <= 0:
                continue
            extent = -360.0 * v / total
            canvas.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=start, extent=extent, fill=color, outline=BG, width=1,
            )
            start += extent
        lx = w * 0.62
        ly = h * 0.16
        for label, v, color in items:
            pct = 100.0 * v / total
            canvas.create_rectangle(lx, ly, lx + 12, ly + 12, fill=color, outline="")
            canvas.create_text(
                lx + 18, ly + 6, anchor="w",
                text=f"{label}  {pct:.1f}%", fill=TEXT, font=font,
            )
            ly += 24


def run_app(interval: int = 30, save: bool = False) -> int:
    load_env()
    root = tk.Tk()
    BalanceApp(root, interval=interval, save=save)
    root.mainloop()
    return 0