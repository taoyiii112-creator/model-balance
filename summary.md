# 开发记录

## 日期：2026-08-07

完成：手机 App 用量页新增图表——按天柱状图（消费金额 / Token 可切换）与 Token 构成扇形图（输入命中缓存 / 未命中缓存 / 输出）；UsageRecord 与 SQLite 增加缓存 Token 字段（v2 迁移），记录对话框拆分输入 Token。analyze 零问题、11 个测试通过，APK 已重新打包（49.6MB）。

影响：Token 用量从纯列表升级为可视化统计，可直观看到每日消费与 Token 构成。

备注：余额趋势图与低余额告警仍待做。

## 日期：2026-08-07

完成：手机 App 实机首测发现发布版无法联网查询余额——Flutter 默认只在 debug 清单提供 INTERNET 权限，release 打包缺失；已在主 AndroidManifest 补上权限并重新打包（应用名同步改为「模型余额」），commit ba7924f。

影响：修复后 release APK 可正常访问 api.deepseek.com 等余额接口。

备注：待用户重装新 APK 实机确认。

## 日期：2026-08-07

完成：手机 App APK 打包成功。安装 Android SDK 36.1.0（D:\Android\Sdk，含 platform-tools / Android 36 平台 / build-tools 36.1.0）；因 services.gradle.org 直连下载失败，将 Gradle 发行版切到腾讯镜像、Maven 依赖切到阿里云镜像（配置已写入 App README）；flutter build apk 产出 release 安装包 app-release.apk（48.7MB，debug 签名，可直接安装）。

影响：模型余额手机 App 可安装到 Android 手机实机使用。

备注：当前为 debug 签名，正式发布需配置正式签名密钥；待实机验证功能。

## 日期：2026-08-07

完成：手机 App 工程化。安装 Flutter SDK 3.44.8（D:\flutter\flutter，使用中国镜像 pub.flutter-io.cn / storage.flutter-io.cn）；flutter create 生成 android/ios 平台工程；flutter analyze 零问题；flutter test 7 个测试全部通过。

影响：模型余额手机 App 从纯代码骨架变为可编译验证的工程，可在 VS Code 中打开开发调试。

备注：Android SDK 未安装，打包 APK 待装工具链（可后续安装 Android Studio 或 commandline-tools）。

## 日期：2026-08-06

完成：新增手机 App（Flutter）项目 D:\codexProject\model_balance_app：余额实时查询（DeepSeek / OpenAI / 中转渠道）、Token 用量记录（SQLite）、API Key 安全存储、账户管理，并附解析单测与首页 Widget 测试。

影响：模型余额可在手机端实时查看，复用桌面版的多提供商适配器设计。

备注：本机尚未安装 Flutter SDK 与 Android 工具链，待安装后运行 flutter pub get / test / analyze 验证并打包 APK。

## 日期：2026-08-06

完成：新增 Windows 桌面应用（Tkinter 界面，余额表 + 用量表 + 自动刷新，后台线程查询不卡界面），通过真实数据验证（DeepSeek 余额 0.30 元）。用户确认应用形态为桌面应用，Web 仪表盘降为可选。

影响：核心目标"实时获取余额"以桌面应用形式落地，无需浏览器；双击 启动仪表盘.bat 即可使用。

备注：中转渠道与 OpenAI 官方待配置真实 Key / 地址后验证。

## 日期：2026-08-06

完成：DeepSeek 真实余额验证通过（余额约 0.36 元，官方接口实时返回）；代码上传 GitHub（taoyiii112-creator/model-balance，main 分支）。

影响：核心目标"实时获取余额"在 DeepSeek 上全链路打通（官方接口 → CLI → 界面）。

备注：中转渠道与 OpenAI 官方待配置真实 Key / 地址后验证。

## 日期：2026-08-06

完成：展示层落地为本地 Web 仪表盘；新增 OpenAI 官方余额适配器（credit_grants，稳定性待真实 Key 验证）；生成 .env 模板。

影响：核心链路（余额查询 + 用量记录 + 实时展示）全部具备。

备注：多数主流平台（Anthropic / Gemini / 通义 / Kimi）无公开余额接口。

## 日期：2026-08-06

完成：第一阶段骨架。选定技术栈（Python 3 标准库 + SQLite）；实现 DeepSeek 与 OpenAI 兼容中转渠道余额查询、Token 用量本地记录、watch 实时轮询。

影响：核心链路（余额查询 + 用量记录）可离线演示。

备注：项目按用户要求固定在 D:\codexproject\模型余额。

## 日期：2026-08-05

完成：项目初始化。创建 README / memory / todo / summary 四件套文档，初始化 Git 仓库（main 分支）。

影响：确立项目核心目标——实时获取模型 API 余额（多少钱）与 Token 用量。

备注：技术栈与应用形态待用户确认后进入开发。
