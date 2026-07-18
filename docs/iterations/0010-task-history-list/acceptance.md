# ITER-0010 Acceptance

> 状态：Completed
> 更新日期：2026-07-08

## 必选验收

- [x] 内存 Store 可列出最近任务摘要。
- [x] SQLite Store 可列出最近任务摘要。
- [x] 列表按完成时间倒序。
- [x] 列表不包含完整 steps、Observation、UI tree 或截图。
- [x] HTTP API 支持 `GET /v1/tasks?limit=N`。
- [x] CLI 可渲染任务列表和空状态。
- [x] limit 限制在 1 到 100。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_task_runner runtime.tests.test_sqlite_task_store runtime.tests.test_task_list_cli -v` | 13 tests, OK |
| `python3.11 -m py_compile runtime/mobile_agent/api/server.py runtime/mobile_agent/cli/task_list.py runtime/mobile_agent/storage/sqlite.py runtime/mobile_agent/tasks/store.py runtime/mobile_agent/runtime.py runtime/tests/test_task_list_cli.py` | OK |
| `make check` | 78 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不新增真实设备动作，使用 Fake Adapter 和临时 SQLite 验证历史列表。
