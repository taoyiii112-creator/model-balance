# 项目目标

用户定义（不得修改方向）：

- 核心目标：实时获取模型 API 的余额与用量
  - 余额：账户里有多少钱（可用金额）
  - 消费：已经花了多少钱
  - 用量：使用了多少 Token（含输入命中缓存 / 未命中缓存 / 输出构成）
- 应用形态：桌面应用（不是网站），已确认

# 当前状态

- 2026-08-07：用量图表完成——桌面与网页版均支持"按天消费金额/Token 柱状图"与"输入(命中缓存)/输入(未命中缓存)/输出 扇形图"；数据模型新增缓存命中拆分字段（旧库自动迁移）；CLI add-usage 支持 --cache-hit/--cache-miss。
- 2026-08-07：手机 App APK 打包成功（app-release.apk 48.7MB，Android SDK 36.1.0 + 腾讯/阿里云构建镜像），待实机安装验证。
- 2026-08-07：手机 App 工程化完成——Flutter 3.44.8 已装（中国镜像）、android/ios 平台工程已生成、flutter analyze 零问题、7 个测试通过。
- 2026-08-06：桌面应用完成并通过真实数据验证（DeepSeek 余额实时显示）。入口：双击 启动仪表盘.bat 或 python run.py app。
- 2026-08-06：DeepSeek 真实余额验证通过；代码已上传 GitHub（https://github.com/taoyiii112-creator/model-balance）。
- 2026-08-05：项目初始化完成；项目按要求迁移至 D:\codexproject\模型余额。

# 技术方案

- 语言/依赖：Python 3.10+，纯标准库（urllib / sqlite3 / argparse / http.server / tkinter），无第三方依赖。
- 架构：多提供商适配器模式（providers/ 下按提供商实现 fetch_balance），账户清单在 config.json，密钥放 .env。
- 存储：SQLite（data/balance.db），usage_records 含 prompt_cache_hit_tokens / prompt_cache_miss_tokens（旧库自动 ALTER 迁移）；balance_snapshots 存余额快照。
- 聚合：storage.usage_daily（按天消费/Token，零值补齐）与 storage.usage_breakdown（缓存命中/未命中/输出）。
- 图表：桌面应用用 Tkinter Canvas 绘制柱状图与扇形图；网页版用 Canvas JS 绘制（无第三方图表库）。
- 展示层（主）：桌面应用 app.py（Tkinter），余额表 + 用量表 + 图表 + 自动刷新。
- 展示层（可选）：web 命令本地仪表盘。
- 入口：run.py / python -m modelbalance；Windows 双击 启动仪表盘.bat。
- 实时性：桌面应用定时刷新（默认 30 秒，可调）+ watch 命令行轮询。

# 开发规范

- 文档与代码同步维护（README / memory / todo / summary 四件套）。
- 子项目（如手机 App `D:\codexProject\model_balance_app`）不重复建四件套：仅保留 README.md，进度文档由父项目统一维护。
- Git 提交信息用中文，遵循 feat: / fix: / refactor: / docs: / chore: / test: 前缀。
- 敏感信息（API Key、Token）一律放 .env，永不提交到 Git。
- 一个提交只做一件事。
- 所有正式项目必须位于 D:\codexproject 下（项目工作流技能强制规则）。

# 已知问题

- DeepSeek 官方余额接口只返回总额/可用，不返回"已用金额"，已用列显示"-"。
- 中转渠道尚未配置真实地址与 Key（config.json 中 base_url 为示例域名）。
- OpenAI credit_grants 接口对部分 API Key 不稳定，待真实 Key 验证。
- 各提供商余额接口不统一：Anthropic / Gemini / 通义 / Kimi 无公开余额接口。
- 手机 App 表结构尚未同步缓存命中字段与图表（待办）。

# 下一步计划

1. 手机 App 同步缓存命中字段与用量图表。
2. 接入中转渠道：用户提供真实 base_url 并填 RELAY_API_KEY 后验证。
3. 可选：OpenAI 官方 Key 验证。
4. Token 用量自动采集（代理层或渠道用量接口）。
5. 余额趋势图与低余额告警。