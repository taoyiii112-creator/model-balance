# 进行中

- 接入中转渠道：填 RELAY_API_KEY，并把 config.json 的 base_url 改成真实地址（待用户提供）
- 可选：OpenAI 官方（填 OPENAI_API_KEY 后验证）
- 手机 App（Flutter）：v0.2.0（图表 + 应用内更新）已打包，待实机安装验证

# 待完成

- 余额趋势图与低余额告警
- 打包为独立 exe（可选）

# 完成

- 2026-08-07 手机 App 稳定性优化（v0.2.2）：更新下载流程修复、SHA256 校验、正式签名、按币种汇总、用量编辑删除、后台暂停刷新
- 2026-08-07 手机 App 更新提示增强（v0.2.1）：显示更新功能说明与更新包大小
- 2026-08-07 手机 App 应用内更新（v0.2.0）：检查 GitHub Release、下载并安装新版本
- 2026-08-07 手机 App 用量图表：每日柱状图 + Token 构成扇形图（与桌面/网页版同步，缓存命中字段拆分）
- 2026-08-07 手机端更新源可配置 + 检查失败提示（v0.2.2，待发布 Release）
- 2026-08-07 健壮性优化（v0.2.1）：流式代理 / 更新源可配置 / 更新包校验清理 / 并行查询 / busy_timeout
- 2026-08-07 桌面版自动更新（GitHub Releases 检查/下载/应用）
- 2026-08-07 桌面应用/网页版自动拉起用量代理（无需手动启动）
- 2026-08-07 本地 API 代理自动采集 Token 用量（proxy 命令，流式/非流式均支持）
- 2026-08-07 用量图表：桌面与网页版按天消费/Token 柱状图 + 输入输出构成扇形图；数据模型缓存命中拆分（旧库自动迁移）
- 2026-08-07 手机 App APK 打包成功：安装 Android SDK 36.1.0，构建源切换为腾讯/阿里云镜像，flutter build apk 产出 app-release.apk（48.7MB）
- 2026-08-07 手机 App 工程化：Flutter SDK 3.44.8 安装（中国镜像）、生成 android/ios 平台工程、flutter analyze 零问题、7 个测试通过
- 2026-08-06 手机 App 项目创建：Flutter 骨架 + 余额查询（DeepSeek / OpenAI / 中转渠道）+ Token 用量记录 + API Key 安全存储 + 账户管理
- 2026-08-06 桌面应用（Tkinter 窗口，实时刷新）完成并通过真实数据验证
- 2026-08-06 DeepSeek 真实余额验证通过（官方接口实时返回，桌面应用实时显示）
- 2026-08-06 上传 GitHub（https://github.com/taoyiii112-creator/model-balance）
- 2026-08-06 本地 Web 仪表盘（保留为可选）+ OpenAI 官方余额适配器
- 2026-08-06 项目骨架：多提供商适配器框架 + DeepSeek / OpenAI 兼容渠道余额查询 + CLI + SQLite 用量与快照存储
- 2026-08-05 项目初始化：创建 README / memory / todo / summary 文档与 Git 仓库
