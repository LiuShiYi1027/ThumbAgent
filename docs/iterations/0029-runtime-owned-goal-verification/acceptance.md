# ITER-0029 Acceptance

> 状态：Completed
> 更新日期：2026-07-14

- [x] AgentGoalAcceptance 至少包含一个成功条件，未知字段被拒绝。
- [x] 所有指定的 app id、Activity 和 Selector 条件必须同时满足。
- [x] 外部验收满足时，即使模型 `finish` Selector 语义脆弱，任务仍由 Runtime 验证成功。
- [x] 外部验收不满足时产生可恢复 failed round，不伪装成功。
- [x] 未提供外部验收时保持现有模型 `finish` 行为。
- [x] TaskRun 持久化 `goal_acceptance` 和 `completion_source`。
- [x] Web/CLI 展示完成来源与验收摘要。
- [x] AgentEvaluationScenario 复用验收 Contract 并支持 Activity。
- [x] API 无效验收返回 `INVALID_ARGUMENT`，不调用模型或设备动作。
- [x] `make check` 通过（149 tests）。
- [x] 真机任务使用 Runtime-owned acceptance 成功完成。

## 验证命令

```bash
make check
```

真机 E2E 必须显式运行，不进入默认测试集。

## 真机结果

- 设备：Android 16，`adb:A6TG025A13002156`。
- Provider：`openai_compatible`，状态 active。
- 起始状态：荣耀桌面。
- 动态路径：点击设置 → 点击显示和亮度 → 模型请求 `finish`。
- 最终 Activity：`.Settings$DisplaySettingsActivity`。
- Task：`task_1ae4f92ae76b423d8202c29bcfebae2e`，3 rounds，succeeded。
- 完成来源：`runtime_acceptance`。
