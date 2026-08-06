# 模型余额获取

## 项目介绍

Windows 桌面应用，实时获取模型 API 账户余额与用量：

- 余额：账户里还剩多少钱（可用金额）
- 消费：已经花了多少钱
- 用量：累计使用了多少 Token

当前能力：

- 桌面应用（Tkinter 窗口，自动刷新，无需浏览器）
- DeepSeek 官方余额查询（真实验证通过）
- OpenAI 官方余额查询（接口稳定性待真实 Key 验证）
- OpenAI 兼容中转渠道（one-api / new-api 类）余额查询
- 本地 SQLite 记录 Token 用量与余额快照
- CLI 单次查询、实时轮询监控（watch）
- 可选：本地 Web 仪表盘（网页版，双击 `启动网页版.bat` 自动打开浏览器）

## 快速开始

1. 双击 `启动仪表盘.bat`，或命令行运行 `python run.py app`。
2. 应用窗口打开后自动查询余额并每 30 秒刷新（可在窗口里改间隔）。
3. 首次使用请先配置：复制 `.env.example` 为 `.env`（项目已生成 .env 模板）填入 API Key，再按需编辑 `config.json`。

CLI 其他命令：

```
python run.py balance                    # 查询所有账户余额
python run.py balance --save             # 查询并保存余额快照
python run.py watch --interval 60 --save # 实时监控，每 60 秒刷新并保存
python run.py web                        # 可选：本地仪表盘，浏览器打开 http://127.0.0.1:8000
python run.py usage --since 7            # 查看最近 7 天 Token 用量
python run.py add-usage --account deepseek-main --model deepseek-chat --prompt 1000 --completion 500 --cost 0.12
```

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

## 主流平台余额接口说明

| 平台 | 余额接口 | 说明 |
| --- | --- | --- |
| DeepSeek | 有（user/balance） | 已接入并验证 |
| OpenAI | 有（credit_grants） | 已接入，但对部分 API Key 不稳定，需验证 |
| 中转渠道（one-api 等） | 有（user/status） | 已接入，待配置真实地址验证 |
| Anthropic / Gemini / 通义千问 / Kimi | 无公开余额接口 | 无法查余额，Token 用量走本地记录 |

## 环境要求

- Python 3.10+（Windows 自带 Tkinter；项目已内置运行时可用）
- Windows / macOS / Linux 均可（桌面应用面向 Windows）

## 备注 / 相关项目

本应用另有手机端（Flutter）项目：`D:\codexProject\model_balance_app`，独立项目，支持 Android / iOS，详见该目录 README.md。Flutter 3.44.8 已安装并通过 `flutter analyze`（零问题）与 `flutter test`（7 个测试通过）；Android SDK 待装，装后即可 `flutter build apk` 打包。
