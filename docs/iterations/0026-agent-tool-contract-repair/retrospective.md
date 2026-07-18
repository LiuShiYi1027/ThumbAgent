# ITER-0026 Retrospective

> 状态：Active
> 更新日期：2026-07-13

## 实际交付

- 新增版本化 `AgentToolCall` Schema，严格校验当前 Agent Tool 参数。
- 点击 Tool 强制显式解析可点击祖先，解决真机 `TARGET_NOT_CLICKABLE` 的直接原因。
- OpenAI-compatible Provider 在无效输出时最多修复一次，并在 Decision 中记录修复次数。
- 已验证 ToolCall 的执行失败保留当轮 Observation 和 Decision。
- Web 与 CLI 报告可见地标记模型修复次数。

## 偏差与问题

最初只计划修复点击参数；复盘时发现这是所有模型 ToolCall 的通用契约问题，因此同步收紧了
`app.launch`、`input.swipe` 和 navigation 的参数形状。没有增加新 Tool 或改变架构依赖方向。

## 验证结果

- 定向 Agent/Provider/Web/CLI 测试：32 项通过。
- `make check`：lint、typecheck 和 126 项单元/集成测试全部通过。
- JSON Schema 文件已通过 JSON 语法校验，`git diff --check` 通过。
- 真机模型 E2E 已通过：模型生成带 `resolve_clickable_ancestor=true` 的点击，页面变化后再次 Observation，最终由 Runtime 验证“显示和亮度”并成功结束。

## 后续行动

- 后续建立版本化 Agent 评测集，将真机中发现的失败轨迹转为离线回放用例。
