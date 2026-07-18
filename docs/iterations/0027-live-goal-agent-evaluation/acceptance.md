# ITER-0027 Acceptance

> 状态：Active
> 更新日期：2026-07-13

## 验收标准

- [x] 场景只定义目标、最终状态、禁用 Tool 和预算，不包含标准动作序列。
- [x] 评测器不调用 Planner、ToolRuntime 或 DeviceAdapter。
- [x] 最终前台 App 和 UI Selector 可独立于模型 reason 验证。
- [x] 禁用 Tool、Policy 违规和轮次超预算会导致评测失败。
- [x] 结果包含轮次、Tool、changed/unchanged、模型修复、违规和耗时指标。
- [x] API 仅读取已持久化 TaskRun，不重放设备动作。
- [x] CLI、lint、typecheck 和默认测试集通过。

## 验证命令

```bash
PYTHONPATH=runtime python3.11 -m unittest \
  runtime.tests.test_agent_evaluator \
  runtime.tests.test_api_security \
  runtime.tests.test_task_evaluate_cli

make check
```

## 真实 E2E 原则

- 执行任务时必须使用待评真实模型和真实 App 当前版本。
- 可以有任意多条合法路径，不比较历史 ToolCall 相似度。
- 真机测试显式运行，不进入默认快速测试集。
