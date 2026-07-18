# ITER-0011: Local Web Task UI

> 状态：Completed
> 更新日期：2026-07-09
> Owner：Codex

## 目标

在 Runtime 内提供第一版本地 Web UI，让用户可以通过浏览器查看任务历史和任务报告详情。

本迭代要证明：

> Mobile Agent 不再只能通过 CLI 查看任务，而是已经具备可视化产品雏形。

## 背景

ITER-0008 到 ITER-0010 已经完成 CLI 报告、SQLite 持久化和历史任务列表。下一步需要让产品形态更直观，但直接引入 Tauri/Electron/前端构建会扩大工程复杂度。

因此本迭代采用无构建、无依赖的本地 Web UI：由 Runtime 直接提供 `/ui`，页面只调用现有 GET API。

## 范围

- 新增单文件本地 Web UI。
- Runtime HTTP Server 提供：
  - `GET /ui`
  - `GET /ui/`
- 页面展示：
  - 最近任务列表。
  - 任务报告详情。
  - 步骤。
  - 证据摘要。
  - 事件。
  - 失败原因。
- 补齐 UI asset 和 HTML 响应测试。

## 非目标

- Tauri/Electron 桌面壳。
- 前端构建系统。
- 登录、多用户或远程访问。
- 新增写动作或任务启动按钮。
- 实时进度推送。
- Artifact 内容预览。

## 安全边界

- `/ui` 仅在 loopback Runtime 下提供。
- 页面只调用现有 GET API，不触发设备动作。
- 页面不展开完整 UI tree、截图内容或敏感输入。
- POST API 仍受本地 token、Content-Type 和 Origin 约束。

## 依赖

- ITER-0010 的任务列表 API。
- ITER-0007 的任务详情和事件 API。

## 风险

- 单文件 UI 不适合长期复杂交互，但足够验证产品信息架构。
- 当前 GET API 尚未要求 token；V1 仅允许 Runtime 监听 loopback，后续桌面壳需要更严格的本地访问策略。

## 里程碑

1. 新增静态 UI asset。
2. HTTP Server 接入 `/ui`。
3. 补测试。
4. 更新 README、技术方案、迭代索引和复盘。
5. 全量质量门禁通过。

## 完成条件

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
