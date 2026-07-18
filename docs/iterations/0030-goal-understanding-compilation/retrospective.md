# ITER-0030 Retrospective

> 状态：Completed
> 更新日期：2026-07-14

## 实际交付

- 新增 `AgentGoalSpec` 公共 Contract、可替换 GoalCompiler 和 OpenAI-compatible 实现。
- 新增无设备副作用的 `POST /v1/goals/compile`。
- `agent.run` 支持已确认 GoalSpec，以 execution_goal 规划并在 TaskRun 保留 source_goal。
- Web 支持解析、审阅、确认运行；Web/CLI 报告展示完整 GoalSpec。
- LLM 来源的 GoalSpec 在 Contract 和 Runtime 两层强制确认，不能只靠前端按钮约束。

## 验证结果

- `make check` 通过：lint、类型检查和 158 个测试。
- 真机任务 `task_33b8414c5f6d4914b08dff63488398dc` 从桌面动态完成蓝牙页面导航。
- 未确认请求返回 `CONFIRMATION_REQUIRED`；确认后执行 4 rounds 并成功。
- TaskRun 中 `goal` 保持原始短目标，`goal_spec.execution_goal` 保存增强意图。

## 偏差与后续

- Compiler 未生成不可靠 acceptance，因此本次最终状态继续使用 Planner `finish` 确定性验证。
- 首次 finish 发生文本歧义，既有可恢复验证机制使模型改用唯一 resource id 后成功。
- 编译约 22 秒，完整任务约 231 秒；同步 API 在执行期间没有增量事件，是下一阶段明显的产品体验缺口。
- GoalSpec 暂不持久化为独立草稿资源，也没有编辑历史或组合验证器。
