# 开发记录

## 日期：2026-08-06

完成：DeepSeek 真实余额验证通过（余额约 0.36 元，官方接口实时返回）；代码上传 GitHub（taoyiii112-creator/model-balance，main 分支 5 个提交）。

影响：核心目标"实时获取余额"在 DeepSeek 上全链路打通（官方接口 → CLI → Web 仪表盘）。

备注：中转渠道与 OpenAI 官方待配置真实 Key / 地址后验证。

## 日期：2026-08-06

完成：展示层落地为本地 Web 仪表盘（纯标准库 http.server，页面定时轮询余额与用量接口实现实时刷新）；新增 OpenAI 官方余额适配器（credit_grants，稳定性待真实 Key 验证）；生成 .env 模板。

影响：核心链路（余额查询 + 用量记录 + 实时展示）全部具备。

备注：多数主流平台（Anthropic / Gemini / 通义 / Kimi）无公开余额接口。

## 日期：2026-08-06

完成：第一阶段骨架。选定技术栈（Python 3 标准库 + SQLite，CLI 先行）；实现 DeepSeek 与 OpenAI 兼容中转渠道余额查询、Token 用量本地记录、watch 实时轮询。

影响：核心链路（余额查询 + 用量记录）可离线演示。

备注：应用形态展示层后置；项目按用户要求固定在 D:\codexproject\模型余额。

## 日期：2026-08-05

完成：项目初始化。创建 README / memory / todo / summary 四件套文档，初始化 Git 仓库（main 分支）。

影响：确立项目核心目标——实时获取模型 API 余额（多少钱）与 Token 用量。

备注：技术栈与应用形态待用户确认后进入开发。