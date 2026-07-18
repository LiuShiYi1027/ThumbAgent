# ITER-0012 Retrospective

> 状态：Active
> 更新日期：2026-07-09

## 实际交付

- Web UI 增加在线设备选择。
- Web UI 增加“运行安全 Demo”按钮。
- Demo 固定调用 `POST /v1/tasks/settings.scroll_navigate/run`，进入显示/亮度页面。
- `/ui` 注入 Runtime token，浏览器 POST 使用 `Authorization: Bearer ...`。
- POST Origin 允许同源 loopback 页面，仍拒绝任意外部 Web Origin。
- 新增/更新 Web UI、语义导航和 API 安全测试。

## 验收结果

- 定向测试 5 tests OK。
- 全量 `make check` 81 tests OK，lint/typecheck OK。
- `git diff --check` OK。

## 计划偏差

- 本迭代没有做通用任务创建器，只做固定 demo。这样能先验证从 Web UI 发起受控任务的产品闭环。

## 有效做法

- 复用已有 `settings.scroll_navigate` 任务 API，没有新增底层设备动作。
- 浏览器 POST 仍使用 Runtime token，避免为了 UI 方便绕过已有 POST 安全边界。
- 任务完成后自动刷新列表并打开报告，形成“启动 → 记录 → 报告”的闭环。

## 问题与根因

- demo selector 目前面向中文系统设置，通过 `contains: 亮度` 兼容“显示与亮度”和“显示和亮度”；非中文系统仍可能无法命中。
- 真实设备反馈默认滚动幅度容易过头，已将 Web demo 调整为 35% 屏高的小步滚动，并增加滚动次数预算。
- Demo 仍依赖真实设备已经开启 USB 调试和 USB 调试安全设置。

## 长期文档回写

- README 和技术方案已记录 Web UI demo 按钮和安全边界。
- 本迭代未改变 Contract、持久化 Schema 或核心安全信任模型，不需要 ADR。

## 后续行动

- 下一步可以做多语言 demo selector、设备厂商滚动策略或把 demo 任务配置化。
- 也可以开始做 Tauri 桌面壳，复用现有 `/ui` 信息架构。
