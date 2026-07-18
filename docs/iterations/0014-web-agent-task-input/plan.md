# ITER-0014 Web Agent Task Input

> 状态：Completed
> 更新日期：2026-07-09

## 背景

ITER-0013 已经提供 `POST /v1/tasks/agent.run`，但入口仍停留在 API 层。为了让产品形态更贴近 AI Native，需要在本地 Web UI 中提供自然语言任务输入，让用户能从页面发起 Agent Loop Preview。

## 目标

在 `/ui` 增加一个最小自然语言任务输入区：

```text
选择设备
    → 输入目标
    → 点击运行 Agent Preview
    → 调用 POST /v1/tasks/agent.run
    → 刷新任务列表并打开报告
```

## 范围

### 本迭代实现

- Web UI 增加自然语言目标输入框。
- Web UI 增加“运行 Agent Preview”按钮。
- 调用已有 `POST /v1/tasks/agent.run`。
- 前端做最小输入校验：必须选择在线设备、目标不能为空。
- 任务完成或失败后刷新历史列表并打开任务报告。
- README、迭代索引和测试同步更新。

### 本迭代不实现

- 不接真实 LLM。
- 不扩展 Agent Preview 支持目标范围。
- 不实现异步后台队列、取消、暂停或流式事件。
- 不新增后端 Contract、存储迁移或设备动作。

## 验收

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
