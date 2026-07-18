# ITER-0006 Acceptance

> 状态：Completed
> 更新日期：2026-07-08

## 必选验收

- [x] `TaskRun` 具有版本化 Contract。
- [x] `TaskRun` 包含 `task_id`、任务类型、设备、目标、状态、开始/完成时间、步骤和证据摘要。
- [x] 第一个任务类型仅包装 `settings.scroll_navigate`，不绕过 Skill/Tool/Policy/Device Gateway。
- [x] 成功任务报告包含最终前台应用、验证节点、Skill 调用 ID 和 tap action ID。
- [x] 缺少 Medium 风险确认时，任务报告保留 `CONFIRMATION_REQUIRED` 错误语义。
- [x] 默认单元测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_task_runner -v` | 4 tests, OK |
| `python3.11 -m py_compile runtime/mobile_agent/domain/task.py runtime/mobile_agent/tasks/runner.py runtime/mobile_agent/runtime.py runtime/mobile_agent/api/server.py` | OK |
| `make check` | 66 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不要求新增真机动作验证。TaskRunner 复用 ITER-0005 已通过的 `settings.scroll_navigate` 真机链路；默认验收使用 Fake Adapter 验证任务报告结构和失败语义。
