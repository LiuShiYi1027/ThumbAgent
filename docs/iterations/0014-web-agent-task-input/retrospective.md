# ITER-0014 Retrospective

> 状态：Active
> 更新日期：2026-07-09

## 实际交付

- Web UI 增加 Agent Preview 目标输入框。
- Web UI 增加“运行 Agent Preview”按钮和目标重置按钮。
- 页面调用 `POST /v1/tasks/agent.run`，POST 仍使用本地 Runtime token。
- 任务返回后刷新历史列表并打开任务报告。
- README 和迭代索引已同步更新。

## 验收结果

- 定向测试 6 tests OK。
- 全量 `make check` 86 tests OK，lint/typecheck OK。

## 计划偏差

- 未扩展 Agent Preview 支持目标范围，符合本迭代范围。

## 有效做法

- 复用已有 `agent.run` 后端入口，没有新增 API 语义。
- 复用同一个在线设备选择器，保持页面简单。
- 空目标只在前端提示，不发起真实设备任务。

## 问题与根因

- 当前输入框虽然是自然语言形态，但后端 Planner 仍是 deterministic preview，只支持显示/亮度目标。

## 长期文档回写

- README 已记录 Web UI Agent Preview 输入入口。
- 本迭代未改变 Contract、持久化 Schema 或安全信任模型，不需要 ADR。

## 后续行动

- 下一步可以接入真实 LLM Planner Provider 的配置与结构化输出校验。
- 也可以先做任务运行中的实时状态展示，避免同步任务期间页面只显示等待文案。
