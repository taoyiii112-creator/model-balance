# 进行中

- 接入中转渠道：填 RELAY_API_KEY，并把 config.json 的 base_url 改成真实地址（待用户提供）
- 可选：OpenAI 官方（填 OPENAI_API_KEY 后验证）

# 待完成

- 按需扩展更多提供商（Anthropic / Gemini / 通义等，注意多数无公开余额接口）
- Token 用量自动采集（代理层或渠道用量接口）
- 余额趋势图与低余额告警

# 完成

- 2026-08-06 DeepSeek 真实余额验证通过（官方接口实时返回，Web 仪表盘实时显示）
- 2026-08-06 上传 GitHub（https://github.com/taoyiii112-creator/model-balance）
- 2026-08-06 本地 Web 仪表盘（web 命令，页面自动刷新）+ OpenAI 官方余额适配器
- 2026-08-06 项目骨架：多提供商适配器框架 + DeepSeek / OpenAI 兼容渠道余额查询 + CLI + SQLite 用量与快照存储
- 2026-08-05 项目初始化：创建 README / memory / todo / summary 文档与 Git 仓库