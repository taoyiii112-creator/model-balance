# 模型余额获取

## 项目介绍

实时获取模型 API 账户余额与用量的工具：

- 余额：账户里还剩多少钱（可用金额）
- 消费：已经花了多少钱
- 用量：累计使用了多少 Token

当前能力：

- DeepSeek 官方余额查询
- OpenAI 兼容中转渠道（one-api / new-api 类）余额查询
- 本地 SQLite 记录 Token 用量与余额快照
- CLI 单次查询与实时轮询监控（watch）

## 快速开始

1. 安装 Python 3.10+（纯标准库实现，无第三方依赖）。
2. 复制 `.env.example` 为 `.env`，填入 API Key。
3. 按需编辑 `config.json` 配置账户。
4. 运行：

```
python run.py balance                    # 查询所有账户余额
python run.py balance --save             # 查询并保存余额快照
python run.py watch --interval 60 --save # 实时监控，每 60 秒刷新并保存
python run.py usage --since 7            # 查看最近 7 天 Token 用量
python run.py add-usage --account deepseek-main --model deepseek-chat --prompt 1000 --completion 500 --cost 0.12
```

## 配置说明

### .env（敏感信息，不提交）

| 变量 | 说明 |
| --- | --- |
| DEEPSEEK_API_KEY | DeepSeek 官方 API Key |
| RELAY_API_KEY | 中转渠道 API Key |

### config.json（账户清单，可提交）

每个账户字段：

| 字段 | 说明 |
| --- | --- |
| name | 显示名称 |
| provider | deepseek / openai_compat |
| api_key_env | 读取 Key 的环境变量名 |
| base_url | openai_compat 必填，如 https://your-relay.example.com |
| extra.quota_denominator | 中转渠道 quota 换算分母，默认 500000 |
| extra.quota_currency | 币种，默认 CNY |

## 环境要求

- Python 3.10+
- Windows / macOS / Linux 均可