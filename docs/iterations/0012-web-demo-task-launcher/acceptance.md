# ITER-0012 Acceptance

> 状态：Completed
> 更新日期：2026-07-09

## 必选验收

- [x] Web UI 展示在线设备选择。
- [x] Web UI 展示安全 demo 任务按钮。
- [x] demo 按钮调用 `POST /v1/tasks/settings.scroll_navigate/run`。
- [x] demo POST 使用 `Authorization: Bearer` token。
- [x] API 仍拒绝非授权 Web Origin。
- [x] API 允许同源 loopback UI Origin。
- [x] demo 使用小步滚动参数，避免单次滑动过头。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_web_ui runtime.tests.test_api_security -v` | 5 tests, OK |
| `python3.11 -m py_compile runtime/mobile_agent/web/task_ui.py runtime/mobile_agent/api/server.py runtime/tests/test_web_ui.py runtime/tests/test_api_security.py` | OK |
| `make check` | 81 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代未自动执行真实设备 demo。用户可在本地启动 Runtime 后从 `/ui` 点击按钮验证；该操作会向已选设备发起真实设置导航任务。
