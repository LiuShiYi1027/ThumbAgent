# ITER-0066 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-09-21

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 空树判定正确区分骨架树与可定位树 | 单测：空 hierarchy、仅无 id 根节点 → empty；可见文本/描述/hint 或 resource_id → 非 empty | 通过（`test_ui_hierarchy` 6 条） |
| A2 | 瞬态空树可恢复 | Fake：前 1–2 次空树、随后有语义节点，任务 succeeded，Planner 只在恢复后被调用 | 通过 |
| A3 | 持续空树可解释失败 | Fake：三次观察皆空 → `failed` + `UI_TREE_EMPTY`，observe_calls ≤ 3，Planner 调用 0 次，终态不是 `NO_PROGRESS` | 通过 |
| A4 | 失败保留证据且脱敏 | error.details 含 observation_id、screenshot artifact id、node_count、semantic_candidate_count、locatable_node_count；不含 UI 文本或 XML 原文 | 通过 |
| A5 | 设置页不回归 | 既有「open display settings」类 Runner 测试仍 succeeded | 通过（全量 724 tests OK） |
| A6 | 空树不派发语义点击/滑动 | 守卫测试：空观察下 tap_element/swipe 在 Adapter 动作前被拒绝 | 通过（tap_element；back 仍允许） |
| A7 | 取消与 Deadline | 空树重试窗口内取消 → cancelled；Deadline → timed_out；不再发起新的 observe | 通过 |
| A8 | 错误码已登记 | `docs/engineering/error-handling.md` 含 `UI_TREE_EMPTY`；可靠性模型写明只读重试与 known_failure | 通过 |
| A9 | 集中全量验证 | 一次 `make check` 全绿 | 通过（lint / typecheck / 724 tests / contracts --check；本环境 `make` 因 Xcode license 无法直接调用，已按 Makefile 等价命令执行） |
| A10 | 真机 | 设置页任务 succeeded。若实验室设备能复现空 dump 页：任务 `failed`/`UI_TREE_EMPTY` 且报告含最后截图引用。不能复现则记 deferred，不以 Fake 宣称真机空树通过 | 设置页通过（Honor BKQ-AN10，`e2e_iter0066.py`，13s，`runtime_acceptance`；hierarchy 81/17/71，非空）。京东空树 **deferred**：本机登录页 `FLAG_SECURE` 使 `screencap` 失败（`OBSERVATION_FAILED`），uiautomator dump 仍有 44 个可定位节点，不是空树。不以 Fake 宣称真机空树通过 |
