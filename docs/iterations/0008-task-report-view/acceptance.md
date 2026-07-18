# ITER-0008 Acceptance

> 状态：Completed
> 更新日期：2026-07-08

## 必选验收

- [x] CLI 可渲染成功任务报告。
- [x] CLI 可渲染失败任务报告。
- [x] 报告包含任务概要、步骤、证据摘要、事件和失败原因。
- [x] 报告不展开完整 Observation、截图或 UI tree。
- [x] CLI 可从 Runtime API 查询 task 和 events。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_task_report_cli -v` | 2 tests, OK |
| `python3.11 -m py_compile runtime/mobile_agent/cli/__init__.py runtime/mobile_agent/cli/task_report.py runtime/tests/test_task_report_cli.py` | OK |
| `make check` | 70 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不新增真实设备动作。CLI 报告视图使用 Fake Adapter 生成的 TaskRun/Event 验证展示逻辑。
