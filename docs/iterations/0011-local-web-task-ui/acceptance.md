# ITER-0011 Acceptance

> 状态：Completed
> 更新日期：2026-07-09

## 必选验收

- [x] Runtime 提供 `/ui` 页面。
- [x] 页面能展示任务历史列表容器。
- [x] 页面能展示任务报告详情容器。
- [x] 页面调用现有任务列表、任务详情和事件 GET API。
- [x] 页面不触发 POST 写动作。
- [x] HTML 响应使用 `Cache-Control: no-store`。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_web_ui runtime.tests.test_api_security -v` | 5 tests, OK |
| `python3.11 -m py_compile runtime/mobile_agent/web/__init__.py runtime/mobile_agent/web/task_ui.py runtime/mobile_agent/api/server.py runtime/tests/test_web_ui.py` | OK |
| `make check` | 80 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不新增真实设备动作；Web UI 只读取已存在任务记录。
