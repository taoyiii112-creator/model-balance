# 进行中

- 用真实 API Key 验证余额查询（DeepSeek / OpenAI / 中转渠道，待用户填 .env 并授权域名）
- 上传 GitHub（待用户提供仓库地址并授权）

# 待完成

- 按需扩展更多提供商（Anthropic / Gemini / 通义等，注意多数无公开余额接口）
- Token 用量自动采集（代理层或渠道用量接口）
- 余额趋势图与低余额告警

# 完成

- 2026-08-06 本地 Web 仪表盘（web 命令，页面自动刷新）+ OpenAI 官方余额适配器
- 2026-08-06 项目骨架：多提供商适配器框架 + DeepSeek / OpenAI 兼容渠道余额查询 + CLI + SQLite 用量与快照存储
- 2026-08-05 项目初始化：创建 README / memory / todo / summary 文档与 Git 仓库