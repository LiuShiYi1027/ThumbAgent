# ITER-0012 Tasks

> 状态：Completed
> 更新日期：2026-07-09

| ID | 状态 | Owner | 任务 |
| --- | --- | --- | --- |
| TASK-0012-01 | done | Codex | Web UI 增加在线设备选择 |
| TASK-0012-02 | done | Codex | Web UI 增加安全 demo 任务按钮 |
| TASK-0012-03 | done | Codex | 页面 POST 使用 Runtime token |
| TASK-0012-04 | done | Codex | API 安全逻辑允许同源 loopback Origin |
| TASK-0012-05 | done | Codex | 补齐测试、README、验收记录和复盘 |

## 进展记录

- 2026-07-09：`/ui` 增加设备下拉框和“运行安全 Demo”按钮。
- 2026-07-09：按钮调用 `POST /v1/tasks/settings.scroll_navigate/run`。
- 2026-07-09：POST 继续要求 Authorization token，并允许同源 loopback Origin。
- 2026-07-09：根据真机反馈将 demo selector 调整为 `contains: 亮度`，并使用小步滚动参数。
