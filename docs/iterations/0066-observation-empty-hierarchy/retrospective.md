# ITER-0066 Retrospective

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-09-21

## 实际交付

- **空树判定**：`ui.hierarchy` 纯函数。可见节点无 text / content_description / hint /
  resource_id 视为空；模型摘要仍只发带文案的节点。仅有 `resource_id` 的输入框可被
  locator 寻址，不算空树。
- **AgentRunner 有界只读恢复**：空树与 XML 损坏共用最多 3 次 observe；空树 settle 0.5s。
  耗尽后 `failed` + `UI_TREE_EMPTY`，不进 Planner，不再落到 `NO_PROGRESS`。
- **派发守卫**：空观察下拒绝 `tap_element` / `swipe`；`back` / `home` / `app.launch` /
  `app.navigate` 不依赖当前树。
- **错误与可靠性**：`UI_TREE_EMPTY` 登记为 device、retryable、known_failure；details 只含
  observation/截图 id 与计数。
- **真机脚本**：`scripts/e2e/e2e_iter0066.py`（设置页回归 + 京东 dump 分类）。

## 验证结果

- 门禁：lint / typecheck / 724 tests / contracts --check。本环境 `make` 因 Xcode license
  无法直接调用，已按 Makefile 等价命令执行。
- 真机 Honor BKQ-AN10（`adb:A6TG025A13002156`，2026-09-21）：
  - 设置页「进入显示和亮度页面」**succeeded**（13s，`runtime_acceptance`）。
  - 设置页 hierarchy：81 节点 / 17 语义候选 / 71 可定位，非空。
  - 京东登录页 `screencap` 失败（`FLAG_SECURE` → `OBSERVATION_FAILED`）；uiautomator dump
    仍有 44 个可定位节点，**不是空树**。空树真机路径记 **deferred**。

## 偏差与限制

- 原计划用京东搜索结果页复现 ITER-0061 空 dump。本机荣耀未登录京东，停在
  `LoginActivity`；该页截图被系统拦截，与空树是不同故障面。
- 空树持续失败仍只由 Fake 覆盖，不以 Fake 宣称真机空树通过。
- `FLAG_SECURE` 导致 Observation 在截图阶段即失败，走不到 `UI_TREE_EMPTY`。若 0067
  需要过登录墙后的京东页，需另处理安全截图层。

## 效率指标

- 迭代窗口：2026-09-21 当天立项到关闭。
- 计划 Task 数：5；无新增/取消。
- 完整 `make check` 次数：1 次等价命令（lint/typecheck/tests/contracts）。
- 真机场景：1 次设置页回归通过；京东空树未复现。

## 后续行动

- ITER-0067：真实 App 带回答案基线（依赖本迭代空树不再空转；本机需已登录或换可观察页）。
- ITER-0068：桌面 Skills 纵向切片（稳定性测试入口）。
- 可选：`OBSERVATION_FAILED` 对 `FLAG_SECURE` 给出更明确错误码，避免与损坏 PNG 混称。
