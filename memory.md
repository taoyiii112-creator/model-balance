# 项目目标

用户定义（不得修改方向）：

- 核心目标：实时获取模型 API 的余额与用量
  - 余额：账户里有多少钱（可用金额）
  - 消费：已经花了多少钱
  - 用量：使用了多少 Token

# 当前状态

- 2026-08-06：展示层落地为本地 Web 仪表盘（web 命令，纯标准库，页面自动刷新）；新增 OpenAI 官方余额适配器（待真实 Key 验证）；.env 模板已生成待填 Key。
- 2026-08-06：第一阶段骨架完成（DeepSeek / 中转渠道适配器 + CLI + SQLite）。
- 2026-08-05：项目初始化完成；项目按要求迁移至 D:\codexproject\模型余额。

# 技术方案

- 语言/依赖：Python 3.10+，纯标准库（urllib / sqlite3 / argparse / http.server），无第三方依赖。
- 架构：多提供商适配器模式（providers/ 下按提供商实现 fetch_balance），账户清单在 config.json，密钥放 .env。
- 存储：SQLite（data/balance.db），两张表——usage_records（用量）、balance_snapshots（余额快照）。
- 入口：run.py / python -m modelbalance。
- 展示层：web 命令启动本地仪表盘（http://127.0.0.1:8000），前端 JS 定时轮询 /api/balances 与 /api/usage 实现"实时"。
- 实时性：watch 命令行轮询 + web 页面自动刷新。

# 开发规范

- 文档与代码同步维护（README / memory / todo / summary 四件套）。
- Git 提交信息用中文，遵循 feat: / fix: / refactor: / docs: / chore: / test: 前缀。
- 敏感信息（API Key、Token）一律放 .env，永不提交到 Git。
- 一个提交只做一件事。
- 所有正式项目必须位于 D:\codexproject 下（项目工作流技能强制规则）。

# 已知问题

- 各提供商余额接口不统一：DeepSeek、OpenAI（不稳定）、中转渠道有接口；Anthropic / Gemini / 通义 / Kimi 无公开余额接口。
- OpenAI credit_grants 接口历史上对部分 API Key 不稳定，需真实 Key 验证，不行则走中转渠道。
- Token 用量目前靠手动记录（add-usage），自动采集需接入代理层或渠道用量接口。
- 真实接口验证需要用户提供 API Key 并允许访问对应域名。

# 下一步计划

1. 上传 GitHub（待用户提供仓库地址并授权网络访问）。
2. 用户填写 .env 的 API Key 后，用真实接口验证 DeepSeek / OpenAI / 中转渠道。
3. 按需扩展更多提供商；多数主流平台无余额接口，重点放在渠道与用量统计。
4. 余额趋势图与低余额告警。