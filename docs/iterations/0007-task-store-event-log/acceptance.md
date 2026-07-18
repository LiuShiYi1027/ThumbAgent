# ITER-0007 Acceptance

> 状态：Completed
> 更新日期：2026-07-08

## 必选验收

- [x] `TaskEvent` 具有版本化 Contract。
- [x] 完成的 `TaskRun` 可通过 `task_id` 查询。
- [x] 每个任务可查询紧凑事件序列。
- [x] 事件序列包含 `task.started`、`task.step_completed` 和 `task.completed`。
- [x] 事件序列号从 1 递增。
- [x] 缺失任务返回 `TASK_NOT_FOUND`，HTTP 映射为 404。
- [x] Store 不绕过 Skill/Tool/Policy 执行链。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_task_runner runtime.tests.test_runtime_service runtime.tests.test_api_security -v` | 11 tests, OK |
| `python3.11 -m py_compile runtime/mobile_agent/domain/task.py runtime/mobile_agent/tasks/store.py runtime/mobile_agent/tasks/runner.py runtime/mobile_agent/runtime.py runtime/mobile_agent/api/server.py` | OK |
| `make check` | 68 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不新增真实设备动作；任务查询和事件日志使用 Fake Adapter 验证。真实设备动作仍复用 ITER-0005 已验证过的 `settings.scroll_navigate` 链路。
