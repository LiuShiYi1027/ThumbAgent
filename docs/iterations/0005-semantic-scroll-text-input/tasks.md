# ITER-0005 Tasks

> 状态：Completed
> 更新日期：2026-07-08

| ID | 状态 | Owner | 任务 |
| --- | --- | --- | --- |
| TASK-0005-01 | done | Codex | 定义滚动、文本输入和语义查找 Contract 与兼容性结论 |
| TASK-0005-02 | done | Codex | 实现 `input.swipe` Tool、Android Adapter 映射与 Fake Adapter 测试 |
| TASK-0005-03 | done | Codex | 实现 `input.text` Tool、可编辑目标校验、文本限制和策略门禁 |
| TASK-0005-04 | done | Codex | 实现有界语义滚动查找、无进展检测和等待/超时语义 |
| TASK-0005-05 | done | Codex | 实现安全示范 Skill 与 Runtime API 映射 |
| TASK-0005-06 | done | Codex | 补齐自动化测试、Contract 测试、错误分支和质量门禁 |
| TASK-0005-07 | cancelled | Codex | Android 真机滚动导航 E2E 已通过；文本输入 E2E 移入后续 demo/test app 验证 |
| TASK-0005-08 | done | Codex | 更新 README、迭代索引和复盘，收口迭代状态 |

## 协作备注

- 本迭代只修改完成上述任务所需的最小模块。
- Contract、Policy、Tool Registry 和 Adapter 是共享热点；并行 Agent 开工前必须先声明任务 ID，避免同时改同一真源。
- 真机 E2E 必须显式执行，不进入默认 `make check`。
- 若实现中发现需要改变 Tool/Skill 分层、安全信任模型或破坏性 Contract，需要先暂停并补 ADR。

## 进展记录

- 2026-07-08：完成 `input.swipe` 与 `input.text` 的最小 Tool 链路。两者均为 Medium 风险、默认确认；Android Adapter 仅使用固定参数数组；Fake Adapter 和自动化测试已覆盖确认门禁、能力声明、参数边界、可编辑目标校验、敏感文本拒绝和固定 ADB 参数。
- 2026-07-08：完成 `find_element_with_scroll` 内部编排能力。它先 Observe 并匹配 Selector，找不到时调用已注册的 `input.swipe`；支持最大滚动次数、总超时、无进展检测、匹配不唯一拒绝和策略确认门禁。
- 2026-07-08：完成 `settings.scroll_navigate` 安全示范 Skill 与 `POST /v1/skills/settings.scroll_navigate/invoke` API 映射。该 Skill 仅允许系统设置包内 Selector，先滚动查找目标，再语义点击并使用 expected selector 验证结果。
- 2026-07-08：默认质量门禁通过（62 tests、lint、typecheck），`git diff --check` 通过。设备 `adb:5f37fd7` 开启 USB 调试安全设置后允许输入注入；真机发现 tap 需要 `input touchscreen tap`，swipe 使用 plain `input swipe` 更稳定。完成 `settings.scroll_navigate` 滚动导航 E2E：目标“显示与亮度”初始不可见，滚动后点击进入，并以 action bar 标题验证成功。文本输入 E2E 因当前系统设置未暴露安全 `EditText` 页面，待后续测试 App 或 demo 页面补做。
