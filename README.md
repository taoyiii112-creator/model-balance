# 模型余额获取

## 项目介绍

Windows 桌面应用，实时获取模型 API 账户余额与用量：

- 余额：账户里还剩多少钱（可用金额）
- 消费：已经花了多少钱
- 用量：累计使用了多少 Token（含输入命中缓存 / 未命中缓存 / 输出构成）

当前能力：

- 桌面应用（Tkinter 窗口，自动刷新，无需浏览器）
- 余额趋势图（近 30 天，快照默认自动保存）与低余额提醒（< ¥5 红色提示）
- 用量图表：按天消费金额 / Token 柱状图 + 输入输出构成扇形图（桌面与网页版）
- DeepSeek 官方余额查询（真实验证通过）
- OpenAI 官方余额查询（接口稳定性待真实 Key 验证）
- OpenAI 兼容中转渠道（one-api / new-api 类）余额查询
- 本地 SQLite 记录 Token 用量与余额快照
- CLI 单次查询、实时轮询监控（watch）
- 可选：本地 Web 仪表盘（网页版，双击 `启动网页版.bat` 自动打开浏览器）

## 快速开始

1. 双击 `启动仪表盘.bat`，或命令行运行 `python run.py app`。
2. 应用窗口打开后自动查询余额并每 30 秒刷新；**Token 用量正式来源为 `codex-usage`（提取 Codex 会话）**，用量代理为可选工具（需要时手动 `python run.py proxy`）。
3. 首次使用请先配置：复制 `.env.example` 为 `.env`（项目已生成 .env 模板）填入 API Key，再按需编辑 `config.json`。

CLI 其他命令：

```
python run.py balance                    # 查询所有账户余额
python run.py balance --save             # 查询并保存余额快照
python run.py watch --interval 60 --save # 实时监控，每 60 秒刷新并保存
python run.py web                        # 可选：本地仪表盘，浏览器打开 http://127.0.0.1:8000
python run.py usage --since 7            # 查看最近 7 天 Token 用量（含缓存命中统计）
python run.py add-usage --account deepseek-main --model deepseek-chat --cache-hit 200 --cache-miss 100 --completion 50 --cost 0.5
```

`codex-usage` 命令：提取 Codex 本地会话（~/.codex/sessions）的真实 Token 用量——`--export <path>` 导出 JSON 供手机端导入，`--save` 写入本地用量库（account=codex，图表默认隐藏该账户，顶部"含Codex用量"可开关）。用量记录只保留最近 14 天（自动清理）。

`add-usage` 参数：`--prompt`（输入 Token 总数）、`--cache-hit`（输入命中缓存）、`--cache-miss`（输入未命中缓存）、`--completion`（输出）、`--cost`（费用）。提供 cache-hit/miss 时 prompt 自动等于两者之和。

## 用量数据来源

- **正式来源：`codex-usage`**——从 Codex 本地会话提取真实 Token 用量（`python run.py codex-usage --save` 入库）。
- **可选：用量代理**——把其他客户端（非 Codex 的工具/脚本）的 base_url 指向本机代理可自动记账；默认不自动启动，需要时手动：

1. 启动代理：双击 `启动用量代理.bat`，或运行 `python run.py proxy`（默认 http://127.0.0.1:8001）。
2. 客户端配置：base_url 改为 `http://127.0.0.1:8001/v1`，API Key 保持原样（必须是 config.json 已配置账户的 Key）。
3. 每次请求自动写入本地数据库，图表实时更新（note 标记为 proxy）。

实时用量接口（供其他端拉取）：

```
GET http://127.0.0.1:8001/api/v1/usage/realtime?minutes=60&account=<可选>
Authorization: Bearer <任一已配置账户的 API Key>
```

返回最近 N 分钟（默认 60）的用量记录 JSON（账户/模型/时间/输入输出 Token/缓存命中拆分），桌面端已在用量汇总显示最新一条。

可选：在 config.json 账户的 extra 里配置单价（每百万 Token），代理会自动估算费用：

```json
"extra": {
  "pricing": { "input": 2.0, "input_cache_hit": 0.5, "output": 8.0 }
}
```

不配置 pricing 时，费用列不记录（Token 照常记录）。

## 更新机制（桌面版）

桌面版从 GitHub Releases 自动检查更新：

- 启动时自动检查；也可点窗口右上角"检查更新"
- 发现新版本会弹窗显示：新版本号、更新内容（Release 说明）、更新包大小
- 一键下载安装：更新包暂存后应用退出再安装，避免覆盖运行中文件失败；完成后自动重启

发布新版本（你更新、别人收到）：

1. 修改 `src/modelbalance/__init__.py` 的 `__version__`（如 0.2.1）。
2. 双击 `打包更新包.bat`（生成 `dist/model-balance-<版本>.zip`）。
3. 在 GitHub 仓库创建 Release：**Tag 字段**填 `v<版本>`（注意是最上面那个 Tag 输入框，不是标题框），上传 zip 到下方"二进制附件区"（不要拖进说明框），描述里写更新内容（App 更新弹窗会显示）。
4. 发布后其他人打开应用即收到更新（版本号、更新内容、包大小），一键下载安装。

自定义更新源（可选）：`python run.py set-update-source <URL>`（reset 恢复默认），或设置环境变量 `MB_UPDATE_SOURCE`，适用于自建服务器/国内镜像。

注意：更新检查默认访问 `api.github.com`，更新包下载走 GitHub 资产地址（github.com 重定向）；更新包下载后会做 zip 完整性校验，安装完成后自动清理。接收方：zip 源码版需 Python 3.10+，exe 版免 Python（见下方打包章节）；更新时保留用户数据（`.env` / `data` / `config.json`）。

## 局域网同步（手机端拉取 Codex 用量）

桌面端可向同一局域网内的手机 App 提供 Codex 用量：

1. 启动：双击 `启动局域网同步.bat`，或运行 `python run.py lan-sync`（默认 0.0.0.0:8002）。
2. 手机端填写电脑局域网 IP（如 192.168.x.x）+ 端口 8002 + 同步令牌。
3. 同步令牌在 `data/lan_sync_token.txt`（首次启动自动生成，gitignore 不提交；泄露只影响用量数据，删除该文件即可重新生成）。
4. Windows 首次运行需在防火墙放行 8002 端口。

接口：`GET /api/codex-usage`（Bearer 令牌鉴权，只读，返回 Codex 用量 JSON）。

## 配置说明

### .env（敏感信息，不提交）

| 变量 | 说明 |
| --- | --- |
| DEEPSEEK_API_KEY | DeepSeek 官方 API Key |
| OPENAI_API_KEY | OpenAI 官方 API Key |
| RELAY_API_KEY | 中转渠道 API Key |

### config.json（账户清单，可提交）

| 字段 | 说明 |
| --- | --- |
| name | 显示名称 |
| provider | deepseek / openai / openai_compat |
| api_key_env | 读取 Key 的环境变量名 |
| base_url | openai_compat 必填，如 https://your-relay.example.com |
| extra.quota_denominator | 中转渠道 quota 换算分母，默认 500000 |
| extra.quota_currency | 币种，默认 CNY |
| alert_threshold（顶层） | 低余额提醒阈值（元），默认 5.0；可在应用顶部栏修改，自动保存 |

## 主流平台余额接口说明

| 平台 | 余额接口 | 说明 |
| --- | --- | --- |
| DeepSeek | 有（user/balance） | 已接入并验证 |
| OpenAI | 有（credit_grants） | 已接入，但对部分 API Key 不稳定，需验证 |
| 中转渠道（one-api 等） | 有（user/status） | 已接入，待配置真实地址验证 |
| Anthropic / Gemini / 通义千问 / Kimi | 无公开余额接口 | 无法查余额，Token 用量走本地记录 |

## 打包为 exe（免 Python 分发）

双击 `打包exe.bat`（或运行 `python build_exe.py`）生成 `dist/model-balance.exe`（单文件，约 12MB，接收方免装 Python）。

- 分发：把 exe 发给对方即可；首次使用需在 exe 同目录放 `.env`（API Key）与 `config.json`（账户），`data/` 目录会自动建在 exe 旁边。
- exe 版更新：检查到新版本时下载 exe 资产，应用退出后自动替换并重启（无需 Python，通过 cmd 辅助脚本完成）。
- 源码版更新仍走 zip + apply_staged.py（需要 Python 3.10+）。

## 环境要求

- Python 3.10+（Windows 自带 Tkinter；项目已内置运行时可用）
- Windows / macOS / Linux 均可（桌面应用面向 Windows）

## 相关项目（备注）

本仓库是桌面端「模型余额获取」。同一应用的手机端（Flutter）为独立子项目，位于 `D:\codexProject\model_balance_app`（纯英文路径以兼容 Android 构建工具）：

- 实时查询 DeepSeek / OpenAI / 中转渠道余额，默认 30 秒自动刷新
- 手机端 Token 用量记录（SQLite）与余额快照，表结构与桌面版一致（含缓存命中字段拆分）
- API Key 保存在手机系统安全存储（Keystore / Keychain），不写明文
- 支持 Android / iOS；详细文档见该子项目 README.md

手机端开发进度文档（memory / todo / summary）由本仓库统一维护。
