# ITER-0030 Acceptance

> 状态：Completed
> 更新日期：2026-07-14

- [x] GoalSpec 严格拒绝未知字段、空目标、越界置信度和无效成功条件。
- [x] 编译阶段不调用设备 Adapter，不产生设备动作。
- [x] 模型 GoalSpec 未显式确认时不能执行。
- [x] 已确认 GoalSpec 使用 execution_goal 规划，同时 TaskRun 保存 source_goal。
- [x] 模型生成的可选 acceptance 仅在确认后交给 Runtime 验证。
- [x] 未提供 GoalSpec 的旧 agent.run 行为保持兼容。
- [x] Web 展示编译草案、假设、置信度、成功条件和确认动作。
- [x] Provider 错误和无效输出保持脱敏、结构化。
- [x] `make check` 通过（158 tests）。
- [x] 真机短目标经过编译后动态完成。

## 真机结果

- 设备：Android 16，`adb:A6TG025A13002156`。
- 原目标：进入蓝牙设置页面。
- 编译结果：补全“打开系统设置、找到蓝牙入口、点击进入并确认到达”，置信度 0.9。
- 未确认请求：HTTP 403，`CONFIRMATION_REQUIRED`，未进入 Agent Runner。
- 动态路径：`app.launch` 设置 → `input.tap_element` 蓝牙 → `finish`。
- 恢复：首次 `finish` 文本匹配 3 个元素；下一轮改用唯一标题 resource id 后成功。
- Task：`task_33b8414c5f6d4914b08dff63488398dc`，4 rounds，succeeded。
- 最终 Activity：`.Settings$BluetoothSettingsActivity`。
