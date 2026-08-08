# 项目目标

用户定义（不得修改方向）：

- 核心目标：实时获取模型 API 的余额与用量
  - 余额：账户里有多少钱（可用金额）
  - 消费：已经花了多少钱
  - 用量：使用了多少 Token（含输入命中缓存 / 未命中缓存 / 输出构成）
- 应用形态：桌面应用（不是网站），已确认

# 当前状态

- 2026-08-08：局域网同步显示优化——应用内显示 `IP: <ip>:8002 | 令牌: 前8位…`，并新增"复制地址 / 复制IP / 复制令牌"按钮（复制到剪贴板，状态栏提示）。41 项测试全过。
- 2026-08-08：桌面端自动采集 Codex 用量——App 启动即同步一次、之后每 30 秒后台增量扫描 ~/.codex 会话入库（批量写入 + 按 note 去重），只保留 14 天；新增 `codex_usage.sync_codex_usage_to_db()` 供 CLI 与 App 共用；CLI `codex-usage --save` 改为同一函数。41 项测试全过。
- 2026-08-08：局域网同步服务完成——lan-sync 命令（0.0.0.0:8002，/api/codex-usage 只读接口），鉴权用专用同步令牌（data/lan_sync_token.txt，非 API Key），手机端已联调。
- 2026-08-08：Codex 本地会话用量提取完成——新增 `codex-usage` 命令（扫描 ~/.codex 会话 JSONL，按 key 去重；汇总 / `--export` 导出 JSON / `--save` 写入本地用量库，note 标记 codex）。
- 2026-08-08：用量代理改为可选——桌面/网页不再自动拉起，用量统计正式来源为 codex-usage；代理需要时手动 python run.py proxy（保留实时接口能力）。
- 2026-08-08：token 数据修正——codex-usage 改为按会话累计值 total_token_usage 取增量（消除 1-2% 高估）；清理演示/测试记录；真实 Codex 用量 2847 条入库（默认 14 天保留）；桌面图表默认排除 codex 账户（可开关）；全屏布局修复（1220x900）。
- 2026-08-08：实时 Token 用量——桌面代理新增 GET /api/v1/usage/realtime（Bearer 认证，minutes/account 参数），桌面应用用量汇总显示最新一条；手机端接入由用户/其他会话负责。
- 2026-08-08：局域网同步改为应用内一键开关——顶部勾选即启动，自动显示局域网 IP（get_lan_ip）与同步令牌，无需命令行；退出自动关闭。
- 2026-08-08：修复 codex 记录时间显示——codex-usage --save 统一保存本地时间（之前存 UTC 导致显示差 8 小时），已重建 3071 条记录。
- 2026-08-08：桌面端 v0.2.3 已发布 GitHub Release（zip + exe 双资产），含：版本显示、阈值可配置、实时用量接口、局域网同步、token 数据修正（14 天保留/图表排除 codex/全屏布局）、代理改可选。
- 2026-08-08：低余额预警阈值改为用户可配置（config.json alert_threshold，应用顶部栏输入框，修改自动保存）。
- 2026-08-08：桌面应用内显示当前版本号（窗口标题 + 顶部栏）；多端数据同步方案设计完成（docs/多端数据同步方案设计.md），待用户确认后实施。
- 2026-08-07：桌面端 v0.2.2 已发布 GitHub Release（zip + exe 双资产），包含：余额趋势图、低余额提醒、exe 打包、日志 / 健康检查、更新暂存机制、冻结模式路径修复、退出时优雅关闭代理。
- 2026-08-07：exe 打包完成（dist/model-balance.exe 约 12MB，免 Python 分发；冻结模式数据目录指向真实项目根）。
- 2026-08-07：余额趋势图与低余额提醒（快照默认自动保存）；更新改为"暂存 → 退出 → 安装 → 重启"；代理健康检查与端口占用校验；data/logs/app.log 日志。
- 2026-08-07：健壮性优化（v0.2.1）与桌面版自动更新（v0.2.0 起）。
- 2026-08-07：手机端最新 v0.2.6 已发布（正式签名 APK + SHA256 校验），flutter test 25 项通过；更新源可配置、用量图表与余额趋势图均完成。
- 2026-08-06：桌面应用完成并通过真实数据验证（DeepSeek 余额实时显示）；代码已上传 GitHub。
- 2026-08-05：项目初始化完成；项目按要求迁移至 D:\codexproject\模型余额。

# 技术方案

- 语言/依赖：Python 3.10+，纯标准库（urllib / sqlite3 / argparse / http.server / tkinter），无第三方依赖。
- 架构：多提供商适配器模式（providers/ 下按提供商实现 fetch_balance），账户清单在 config.json，密钥放 .env。
- 存储：SQLite（data/balance.db），usage_records 含 prompt_cache_hit_tokens / prompt_cache_miss_tokens；balance_snapshots 存余额快照。
- 聚合：storage.usage_daily（按天消费/Token）与 storage.usage_breakdown（缓存命中/未命中/输出）、snapshot_history（趋势）。
- 自动采集：桌面端 App 内置后台线程（每 30 秒）调用 `codex_usage.sync_codex_usage_to_db()` 扫描 Codex 本地会话并增量入库，只保留 14 天；proxy.py 本地 OpenAI 兼容代理仍保留为可选渠道（默认不自动拉起，需手动 python run.py proxy），用量统计正式来源为 codex-usage。
- 图表：桌面应用用 Tkinter Canvas（柱状图、扇形图、余额趋势折线图，柱状图支持悬停提示）；网页版用 Canvas JS。
- 展示层（主）：桌面应用 app.py（Tkinter）；可选 web 本地仪表盘。
- 入口：run.py / python -m modelbalance；Windows 双击 启动仪表盘.bat；分发用 dist/model-balance.exe（免 Python）。
- 更新：updater.py 从 GitHub Releases 拉取最新版本；源码版走 zip 暂存 + apply_staged.py 应用；exe 版下载 exe 资产 + cmd 辅助脚本自替换；均保留 .env / data / config.json；支持自定义更新源（set-update-source / MB_UPDATE_SOURCE）。
- 实时性：桌面应用定时刷新（默认 30 秒，可调）+ watch 命令行轮询。

# 开发规范

- 文档与代码同步维护（README / memory / todo / summary 四件套）。
- 同一应用的不同端（如手机 App `D:\codexProject\model_balance_app`）各自独立维护完整四件套（README / memory / todo / summary），进度文档不并入父项目，端间关系在 README 末尾「备注 / 相关项目」说明。
- Git 提交信息用中文，遵循 feat: / fix: / refactor: / docs: / chore: / test: 前缀。
- 敏感信息（API Key、Token）一律放 .env，永不提交到 Git。
- 一个提交只做一件事。
- 所有正式项目必须位于 D:\codexproject 下（项目工作流技能强制规则）。
- 版本发布必须经用户明确授权（见 gh-release-publish 技能与 AGENTS.md）。

# 已知问题

- DeepSeek 官方余额接口只返回总额/可用，不返回"已用金额"，已用列显示"-"。
- 中转渠道尚未配置真实地址与 Key（config.json 中 base_url 为示例域名）。
- OpenAI credit_grants 接口对部分 API Key 不稳定，待真实 Key 验证。
- 各提供商余额接口不统一：Anthropic / Gemini / 通义 / Kimi 无公开余额接口。
- 桌面端与手机端数据暂不互通（各自本地 SQLite），多端同步未做。

# 下一步计划

1. 接入中转渠道：用户提供真实 base_url 并填 RELAY_API_KEY 后验证。
2. 可选：OpenAI 官方 Key 验证。
3. 为各账户配置 pricing 单价，让代理自动估算费用。
4. 多端数据同步：按已完成的方案设计（docs/多端数据同步方案设计.md）确认部署/存储/认证后，实施 P1 后端 → P2 桌面 → P3 手机。
5. 分发优化：若 exe 版仍有中文路径临时目录清理弹窗，提供一键启动器（ASCII TMP）。
