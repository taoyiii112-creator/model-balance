# 项目目标

用户定义（不得修改方向）：

- 核心目标：实时获取模型 API 的余额与用量
  - 余额：账户里有多少钱（可用金额）
  - 消费：已经花了多少钱
  - 用量：使用了多少 Token

# 当前状态

- 2026-08-06：第一阶段骨架完成。技术栈选定（Python 3 标准库 + SQLite，CLI 先行）；已实现 DeepSeek 与 OpenAI 兼容中转渠道（one-api / new-api 类）余额查询、Token 用量本地记录、watch 实时轮询。
- 2026-08-05：项目初始化完成；项目按要求迁移至 D:\codexproject\模型余额。

# 技术方案

- 语言/依赖：Python 3.10+，纯标准库（urllib / sqlite3 / argparse），无第三方依赖，便于直接运行。
- 架构：多提供商适配器模式（providers/ 下按提供商实现 fetch_balance），账户清单在 config.json，密钥放 .env。
- 存储：SQLite（data/balance.db），两张表——usage_records（用量）、balance_snapshots（余额快照）。
- 入口：run.py / python -m modelbalance，子命令 balance / watch / usage / add-usage / init-db。
- 实时性：watch 轮询（默认 60 秒），后续可加 Web 仪表盘与告警。

# 开发规范

- 文档与代码同步维护（README / memory / todo / summary 四件套）。
- Git 提交信息用中文，遵循 feat: / fix: / refactor: / docs: / chore: / test: 前缀。
- 敏感信息（API Key、Token）一律放 .env，永不提交到 Git。
- 一个提交只做一件事。
- 所有正式项目必须位于 D:\codexproject 下（项目工作流技能强制规则）。

# 已知问题

- 各提供商余额接口不统一：DeepSeek 有官方余额接口；中转渠道按 one-api / new-api 约定实现，其他渠道响应结构可能不同，需按需适配。
- OpenAI 官方余额接口对 API Key 不稳定，暂未接入，后续验证。
- Token 用量目前靠手动记录（add-usage），自动采集需接入代理层或渠道用量接口。
- 真实接口验证需要用户提供 API Key 并允许访问对应域名。

# 下一步计划

1. 用真实 API Key 验证 DeepSeek / 中转渠道余额查询（需用户提供 Key 并授权网络访问）。
2. 按用户确认的应用形态做展示层（Web 仪表盘 / 其他）。
3. 扩展更多提供商与 Token 用量自动采集。
4. 余额趋势图与低余额告警。