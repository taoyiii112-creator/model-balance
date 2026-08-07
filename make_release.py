"""打包更新包（排除用户数据/敏感文件），输出 dist/model-balance-<版本>.zip。"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDE = {".git", ".env", "data", "dist", "__pycache__", ".pytest_cache", ".idea", ".vscode"}


def read_version() -> str:
    init = (ROOT / "src" / "modelbalance" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__ = "([^"]+)"', init)
    return m.group(1) if m else "0.0.0"


def main() -> None:
    version = read_version()
    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"model-balance-{version}.zip"
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDE for part in rel.parts):
                continue
            if path.is_file():
                zf.write(path, rel.as_posix())
                count += 1
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"已生成: {out}")
    print(f"文件数: {count} | 大小: {size_mb:.2f} MB")
    print()
    print("发布步骤：")
    print(f"1. 在 GitHub 仓库创建 Release，tag 填 v{version}")
    print("2. 上传上面的 zip 作为资产")
    print("3. 在 Release 描述里写本次更新内容（App 更新提示会显示）")


if __name__ == "__main__":
    main()