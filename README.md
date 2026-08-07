# 模型余额获取

## 手机 App（Flutter）

手机端项目位于 `D:\codexProject\model_balance_app`（独立目录，纯英文路径以兼容 Android 构建工具）：

- 实时查询 DeepSeek / OpenAI / 中转渠道余额，默认 30 秒自动刷新
- 手机端 Token 用量记录（SQLite）与余额快照，表结构与桌面版一致
- API Key 保存在手机系统安全存储（Keystore / Keychain），不写明文
- 支持 Android / iOS；详见该目录下 README.md

注：桌面版已新增缓存命中字段与用量图表，手机端表结构待同步（见父项目 todo）。

## 项目介绍

Windows 桌面应用，实时获取模型 API 账户余额与用量：

- 余额：账户里还剩多少钱（可用金额）
- 消费：已经花了多少钱
- 用量：累计使用了多少 Token（含输入命中缓存 / 未命中缓存 / 输出构成）

当前能力：

- 桌面应用（Tkinter 窗口，自动刷新，无需浏览器）
- 用量图表：按天消费金额 / Token 柱状图 + 输入输出构成扇形图（桌面与网页版）
- DeepSeek 官方余额查询（真实验证通过）
- OpenAI 官方余额查询（接口稳定性待真实 Key 验证）
- OpenAI 兼容中转渠道（one-api / new-api 类）余额查询
- 本地 SQLite 记录 Token 用量与余额快照
- CLI 单次查询、实时轮询监控（watch）
- 可选：本地 Web 仪表盘（网页版，双击 `启动网页版.bat` 自动打开浏览器）

## 快速开始

1. 双击 `启动仪表盘.bat`，或命令行运行 `python run.py app`。
2. 应用窗口打开后自动查询余额并每 30 秒刷新（可在窗口里改间隔）；下方图表展示每日消费/Token 与输入输出构成。
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

`add-usage` 参数：`--prompt`（输入 Token 总数）、`--cache-hit`（输入命中缓存）、`--cache-miss`（输入未命中缓存）、`--completion`（输出）、`--cost`（费用）。提供 cache-hit/miss 时 prompt 自动等于两者之和。

## 用量自动采集（代理模式）

把客户端的 base_url 指向本机代理，所有请求自动记录真实用量（输入 / 输出 / 缓存命中）：

1. 启动代理：双击 `启动用量代理.bat`，或运行 `python run.py proxy`（默认 http://127.0.0.1:8001）。
2. 客户端配置：base_url 改为 `http://127.0.0.1:8001/v1`，API Key 保持原样（必须是 config.json 已配置账户的 Key）。
3. 每次请求自动写入本地数据库，图表实时更新（note 标记为 proxy）。

可选：在 config.json 账户的 extra 里配置单价（每百万 Token），代理会自动估算费用：

```json
"extra": {
  "pricing": { "input": 2.0, "input_cache_hit": 0.5, "output": 8.0 }
}
```

不配置 pricing 时，费用列不记录（Token 照常记录）。

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