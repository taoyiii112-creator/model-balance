"""GitHub Release 发布 / 撤回脚本（配合 gh-release-publish 技能使用）。

用法：
  python scripts/publish_release.py create --repo owner/repo --tag vX.Y.Z \
      --title "标题" --notes-file notes.md --assets a.zip,b.apk --confirm yes
  python scripts/publish_release.py delete --repo owner/repo --tag vX.Y.Z --confirm yes

不带 --confirm yes 时只打印计划并拒绝执行；禁止绕过该确认闸门。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _gh(args: list[str]) -> int:
    print("执行: gh " + " ".join(args))
    return subprocess.run(["gh", *args]).returncode


def _fmt_size(path: Path) -> str:
    size_mb = path.stat().st_size / (1024 * 1024)
    return f"{size_mb:.2f} MB"


def cmd_create(args: argparse.Namespace) -> int:
    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    missing = [a for a in assets if not Path(a).exists()]
    if missing:
        print("资产不存在，已拒绝：", missing)
        return 2
    notes = Path(args.notes_file)
    if not notes.exists():
        print("更新说明文件不存在：", notes)
        return 2

    print("=== 发布计划（未确认，仅展示）===")
    print(f"仓库: {args.repo}")
    print(f"Tag:  {args.tag}")
    print(f"标题: {args.title}")
    print(f"说明文件: {args.notes_file}")
    for a in assets:
        p = Path(a)
        print(f"资产: {p.name} ({_fmt_size(p)})")

    if args.confirm_yes != "yes":
        print("未带 --confirm yes，拒绝执行。")
        return 1

    return _gh(
        [
            "release",
            "create",
            args.tag,
            *assets,
            "--repo",
            args.repo,
            "--title",
            args.title,
            "--notes-file",
            args.notes_file,
        ]
    )


def cmd_delete(args: argparse.Namespace) -> int:
    print("=== 撤回计划（未确认，仅展示）===")
    print(f"仓库: {args.repo}")
    print(f"Tag:  {args.tag}")

    if args.confirm_yes != "yes":
        print("未带 --confirm yes，拒绝执行。")
        return 1

    return _gh(
        [
            "release",
            "delete",
            args.tag,
            "--repo",
            args.repo,
            "--yes",
            "--cleanup-tag",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitHub Release 发布/撤回（带确认闸门）")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="创建 Release")
    create.add_argument("--repo", required=True, help="owner/repo")
    create.add_argument("--tag", required=True, help="如 v1.0.0")
    create.add_argument("--title", required=True, help="Release 标题")
    create.add_argument("--notes-file", required=True, help="更新说明文件路径")
    create.add_argument("--assets", required=True, help="资产文件列表，逗号分隔")
    create.add_argument("--confirm", dest="confirm_yes", default="", help="必须为 yes")
    create.set_defaults(func=cmd_create)

    delete = sub.add_parser("delete", help="撤回 Release（含 tag）")
    delete.add_argument("--repo", required=True, help="owner/repo")
    delete.add_argument("--tag", required=True, help="如 v1.0.0")
    delete.add_argument("--confirm", dest="confirm_yes", default="", help="必须为 yes")
    delete.set_defaults(func=cmd_delete)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
