# 进行中

- 接入中转渠道：填 RELAY_API_KEY，并把 config.json 的 base_url 改成真实地址（待用户提供）
- 可选：OpenAI 官方（填 OPENAI_API_KEY 后验证）
- 手机 App（Flutter）：实机验证中——已修复发布版网络权限并重新打包，待重装新 APK 确认

# 待完成

- Token 用量自动采集（代理层或渠道用量接口）
- 余额趋势图与低余额告警
- 打包为独立 exe（可选）
- 手机 App 打包 APK 并实机验证

# 完成

- 2026-08-07 手机 App 用量可视化：每日柱状图（金额/Token）+ Token 构成扇形图（输入命中/未命中缓存、输出）
- 2026-08-07 手机 App APK 打包成功：安装 Android SDK 36.1.0，构建源切换为腾讯/阿里云镜像，flutter build apk 产出 app-release.apk（48.7MB）
- 2026-08-07 手机 App 工程化：Flutter SDK 3.44.8 安装（中国镜像）、生成 android/ios 平台工程、flutter analyze 零问题、7 个测试通过
- 2026-08-06 手机 App 项目创建：Flutter 骨架 + 余额查询（DeepSeek / OpenAI / 中转渠道）+ Token 用量记录 + API Key 安全存储 + 账户管理
- 2026-08-06 桌面应用（Tkinter 窗口，实时刷新）完成并通过真实数据验证
- 2026-08-06 DeepSeek 真实余额验证通过（官方接口实时返回，桌面应用实时显示）
- 2026-08-06 上传 GitHub（https://github.com/taoyiii112-creator/model-balance）
- 2026-08-06 本地 Web 仪表盘（保留为可选）+ OpenAI 官方余额适配器
- 2026-08-06 项目骨架：多提供商适配器框架 + DeepSeek / OpenAI 兼容渠道余额查询 + CLI + SQLite 用量与快照存储
- 2026-08-05 项目初始化：创建 README / memory / todo / summary 文档与 Git 仓库
