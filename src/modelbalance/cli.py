"""命令行入口：查询余额、查看/记录用量、实时监控、Web 仪表盘、桌面应用。"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta

from .config import load_accounts, load_env
from .logutil import get_logger
from .fetcher import fetch_all
from .models import UsageRecord
from .storage import add_snapshot, add_usage_record, init_db, list_usage_records, usage_breakdown, usage_totals
from .web import serve


def fmt_money(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def print_balances(results) -> None:
    header = f"{'账户':<16}{'提供商':<14}{'币种':<6}{'可用金额':>12}{'已用金额':>12}{'总额':>12}  状态"
    print(header)
    print("-" * 80)
    for r in results:
        if r.ok:
            b = r.balance
            print(
                f"{b.account:<16}{b.provider:<14}{b.currency:<6}"
                f"{fmt_money(b.available):>12}{fmt_money(b.used):>12}{fmt_money(b.total):>12}  OK"
            )
        else:
            print(
                f"{r.account.name:<16}{r.account.provider:<14}{'-':<6}{'-':>12}{'-':>12}{'-':>12}"
                f"  错误: {r.error}"
            )


def cmd_balance(args) -> int:
    accounts = load_accounts()
    if not accounts:
        print("没有配置任何账户，请先编辑 config.json")
        return 1
    results = fetch_all(accounts)
    print_balances(results)
    if args.save:
        saved = 0
        for r in results:
            if r.ok:
                add_snapshot(r.balance)
                saved += 1
        print(f"已保存 {saved} 条余额快照到本地数据库")
    return 1 if any(not r.ok for r in results) else 0


def cmd_usage(args) -> int:
    since = None
    if args.since:
        since = datetime.now() - timedelta(days=int(args.since))
    totals = usage_totals(args.account, since)
    records = list_usage_records(args.account, since)
    print(
        f"记录数: {totals['records']}   "
        f"提示词 Token: {totals['prompt_tokens']}   "
        f"补全 Token: {totals['completion_tokens']}   "
        f"总 Token: {totals['total_tokens']}   "
        f"费用: {totals['cost']:.4f}"
    )
    bd = usage_breakdown(args.account, since)
    print(
        f"  输入(命中缓存): {bd['cache_hit']} | 输入(未命中缓存): {bd['cache_miss']} | 输出: {bd['output']}"
    )
    for rec in records:
        print(
            f"{rec['created_at']}  {rec['account']:<16}{rec['model']:<20}"
            f"p={rec['prompt_tokens']} c={rec['completion_tokens']} t={rec['total_tokens']}"
            f"  费用={rec['cost'] or 0:.4f}  {rec['note']}"
        )
    return 0


def cmd_add_usage(args) -> int:
    hit, miss = args.cache_hit, args.cache_miss
    prompt = args.prompt or (hit + miss)
    rec = UsageRecord(
        account=args.account,
        model=args.model,
        prompt_tokens=prompt,
        completion_tokens=args.completion,
        prompt_cache_hit_tokens=hit,
        prompt_cache_miss_tokens=miss,
        cost=args.cost,
        note=args.note or "",
    )
    rid = add_usage_record(rec)
    print(f"已记录用量 #{rid}（{rec.total_tokens} tokens）")
    return 0


def cmd_watch(args) -> int:
    accounts = load_accounts()
    if not accounts:
        print("没有配置任何账户，请先编辑 config.json")
        return 1
    print(f"开始实时监控（每 {args.interval} 秒刷新一次，Ctrl+C 退出）")
    try:
        while True:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
            results = fetch_all(accounts)
            print_balances(results)
            if args.save:
                for r in results:
                    if r.ok:
                        add_snapshot(r.balance)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n已停止监控")
        return 0


def cmd_web(args) -> int:
    return serve(host=args.host, port=args.port, interval=args.interval, save=args.save)


def cmd_app(args) -> int:
    try:
        from .app import run_app
    except ImportError as exc:
        print(f"无法启动桌面应用: {exc}")
        return 1
    return run_app(interval=args.interval, save=not args.no_save)


def cmd_proxy(args) -> int:
    try:
        from .proxy import run_proxy
    except ImportError as exc:
        print(f"无法启动用量代理: {exc}")
        return 1
    return run_proxy(host=args.host, port=args.port)


def cmd_set_update_source(args) -> int:
    from .updater import get_update_source, set_update_source

    if args.url is None:
        print(f"当前更新源: {get_update_source()}")
        return 0
    if args.url == "reset":
        set_update_source("")
        print(f"已恢复默认更新源: {get_update_source()}")
        return 0
    set_update_source(args.url)
    print(f"更新源已设置: {args.url}")
    return 0


def cmd_init_db(args) -> int:
    init_db()
    print("数据库已初始化")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modelbalance", description="模型 API 余额与用量查询")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bal = sub.add_parser("balance", help="查询所有账户余额")
    p_bal.add_argument("--save", action="store_true", help="查询后保存余额快照到本地数据库")
    p_bal.set_defaults(func=cmd_balance)

    p_usage = sub.add_parser("usage", help="查看本地记录的 Token 用量")
    p_usage.add_argument("--account", help="按账户筛选")
    p_usage.add_argument("--since", help="只看最近 N 天，如 7")
    p_usage.set_defaults(func=cmd_usage)

    p_add = sub.add_parser("add-usage", help="手动记录一次 Token 用量")
    p_add.add_argument("--account", required=True)
    p_add.add_argument("--model", required=True)
    p_add.add_argument("--prompt", type=int, default=0)
    p_add.add_argument("--cache-hit", type=int, default=0, help="输入命中缓存的 Token")
    p_add.add_argument("--cache-miss", type=int, default=0, help="输入未命中缓存的 Token")
    p_add.add_argument("--completion", type=int, default=0)
    p_add.add_argument("--cost", type=float)
    p_add.add_argument("--note")
    p_add.set_defaults(func=cmd_add_usage)

    p_watch = sub.add_parser("watch", help="实时轮询余额（监控模式）")
    p_watch.add_argument("--interval", type=int, default=60)
    p_watch.add_argument("--save", action="store_true", help="每次轮询保存快照")
    p_watch.set_defaults(func=cmd_watch)

    p_web = sub.add_parser("web", help="启动本地 Web 仪表盘（可选）")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=8000)
    p_web.add_argument("--interval", type=int, default=30, help="页面自动刷新秒数")
    p_web.add_argument("--save", action="store_true", help="每次查询保存余额快照")
    p_web.set_defaults(func=cmd_web)

    p_app = sub.add_parser("app", help="启动桌面应用（推荐）")
    p_app.add_argument("--interval", type=int, default=30, help="自动刷新秒数")
    p_app.add_argument("--no-save", action="store_true", help="不自动保存余额快照（默认保存）")
    p_app.set_defaults(func=cmd_app)

    p_proxy = sub.add_parser("proxy", help="启动本地 API 代理（自动记录 Token 用量）")
    p_proxy.add_argument("--host", default="127.0.0.1")
    p_proxy.add_argument("--port", type=int, default=8001)
    p_proxy.set_defaults(func=cmd_proxy)

    p_sus = sub.add_parser("set-update-source", help="查看/设置桌面版更新源地址")
    p_sus.add_argument("url", nargs="?", help="更新源 URL；reset 恢复默认；不带参数查看当前")
    p_sus.set_defaults(func=cmd_set_update_source)

    p_db = sub.add_parser("init-db", help="初始化本地数据库")
    p_db.set_defaults(func=cmd_init_db)

    return parser


logger = get_logger("cli")


def main(argv: list[str] | None = None) -> int:
    logger.info("cli.main 开始，argv=%s", argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args_list = sys.argv[1:] if argv is None else argv
    if not args_list:
        # 双击 exe 无参数时默认打开桌面应用
        args_list = ["app"]
    if args_list == ["--proxy"]:
        from .proxy import run_proxy

        return run_proxy(host="127.0.0.1", port=8001)
    load_env()
    logger.info("load_env 完成")
    init_db()
    logger.info("init_db 完成")
    parser = build_parser()
    args = parser.parse_args(args_list)
    logger.info("解析完成，command=%s", args.command)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())