# ITER-0053 Manual Takeover (Pause & Resume)

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-20

## 产品结果

桌面工作台在执行中的 Agent 任务上提供「暂停（人工接管）/ 恢复执行」控制：用户在安全边界
暂停 Agent 后直接手动操作设备，恢复时 Agent 基于最新画面重新观察并继续规划。任务时间线
与报告明确记录暂停-接管-恢复区间，区分「Agent 做的」和「人接管期间发生的」。

## 背景

ITER-0050–0052 交付了任务执行、时间线、报告和设备画面同屏，但执行中用户只能旁观或取消。
真实使用中常见「Agent 卡在某一步，人顺手点两下就能过去」的场景；取消重跑代价高且丢失
已完成的进展。可靠性模型 §4 的任务状态机已预留 `paused → running`，§10 已声明
「人工接管持有更高优先级锁并暂停 Agent」，ADR-0010 Follow-up 也点名评估人工接管——
本迭代把这些预设语义落地为可用的产品与协议能力。

## 范围

### In Scope

1. Runtime 执行语义：`POST /v1/task-executions/{task_id}/pause` 与 `/resume`（Bearer token，
   沿用 `_authorize_post`），协作式暂停在安全边界（轮次之间）生效；`ExecutionStatus` 增加
   `paused`；`TaskExecution` 增加 `pause_requested`；事件流增加 `task.pause_requested`、
   `task.paused`、`task.resumed`。
2. Contract 演进：task-execution 与 task-event Schema 增补枚举值/字段，重新生成 TS 类型，
   补 Contract 测试。
3. 崩溃恢复：Runtime 重启时 `paused` 与 `running` 一样以 `TASK_INTERRUPTED` 失败，
   不自动续跑（可靠性模型 §9）。
4. 桌面 UI：执行视图暂停/恢复按钮与状态横幅；设备画面栏在暂停期间显示人工接管占位
   （保留最后一帧，不再轮询新截图）；时间线展示新事件类型。
5. 规范同步：reliability-model.md 暂停/接管语义、technical-design-v1.md 迭代段落、
   README 当前进展。

### Out of Scope

- 暂停期间的设备画面直播（暂停即无新截图，属预期行为）
- 多次暂停区间的图形化统计、接管期间的按键级审计
- Web UI（Runtime 内置 /ui）的暂停按钮（仅保证新状态/事件不破坏其渲染）
- 租约等待队列、租约续期事件（ADR-0010 其余 Follow-up）
- iOS/鸿蒙 Adapter

## 设计决策

1. **暂停是控制面操作，不需要高风险确认**。它只减少设备动作，不产生副作用；Bearer token
   即足够鉴权。恢复同样不需要确认（Agent 恢复后每个动作仍走既有 Policy/确认体系）。
2. **安全边界生效，不强杀调用**。与取消/deadline 一致（ADR-0010）：暂停请求持久化后，
   在当前模型或 ADB 调用返回、轮次边界处才真正进入 `paused`。请求后到达边界前，
   `pause_requested=true` 对客户端可见。
3. **复用取消探针，不改 Runner 与任务处理器**。执行器传给 `run_factory` 的取消检查回调
   被包装为控制探针：先在边界处理暂停/恢复/期限，再返回取消状态。Runner 与各任务类型
   （agent.run、日志、性能、诊断包、应用生命周期等 10 类）零改动获得暂停能力。
4. **Deadline 时钟在暂停期间继续走**。暂停不延长任务预算，防止租约被无限期持有；暂停中
   到达 deadline 自动恢复，Runner 下一边界按既有逻辑以 `timed_out` 结束。暂停中被取消
   同样自动恢复并按取消收尾。
5. **暂停期间任务继续持有设备租约**。人通过物理设备操作，不经过 Runtime；租约继续阻止
   其他 Runtime 任务写同一设备。可靠性模型 §10 的「更高优先级锁」在 V1 单机场景即
   人的物理持有，Runtime 侧仅停止派发。
6. **接管区间用事件而非新对象表达**。`task.paused`（含进入时间）与 `task.resumed`
   （payload 带 `takeover: true`、`resume_reason: user|cancel|deadline`）界定区间；
   报告与时间线据此渲染，不新增 Contract 对象。
7. **QUEUED 任务不可暂停**（尚未开始，无边界可停在），返回 409 `TASK_STATE_CONFLICT`；
   终态任务暂停/恢复幂等返回当前状态（与 cancel 行为对称）。
8. **持久化零迁移**。`execution_json`/`event_json` 为 JSON blob，`from_dict` 对缺失的
   `pause_requested` 默认 False；仅恢复查询的 status 列表增加 `'paused'`。
9. **不新增 ADR**：依赖方向、信任模型、风险策略均未变，属 ADR-0010 Follow-up 的落地；
   执行语义变化记录在 reliability-model.md 与本迭代文档。

## 兼容性与风险

- 旧客户端读到未知 `paused` 状态/新事件类型：桌面端与 Runtime 同仓库同步升级；Web UI
  按字符串渲染状态与事件类型，新值可原样显示，不破坏页面。MCP 对状态做透传。
- Contract 变更为纯增补（枚举加值、对象加字段），schema_version 维持 1.0.0（沿用
  ITER-0033 增补 `device_session_id` 的先例），存储旧数据由 `from_dict` 默认值兼容。
- 主要风险：暂停等待循环引入死锁或状态竞争。缓解：所有状态迁移在执行器锁内完成，
  等待循环只做只读检查与带超时的 Event.wait；补并发单元测试（暂停×取消、暂停×deadline）。

## 验证策略

- 单元测试：暂停在边界生效、恢复续跑、暂停×取消、暂停×deadline、幂等与状态冲突、
  持久化往返、SQLite 恢复覆盖 paused。
- API 测试：pause/resume 的 401/404/409/202。
- 桌面：oxlint + tsc；Rust 侧无改动。
- 门禁：完整 `make check` 与 `make check-desktop`。
- 真机 Low 风险：执行 `settings.display-brightness.v1`，执行中暂停（确认不再派发新动作、
  事件正确），人工操作设备后恢复（确认重新观察并完成任务），报告可见接管区间。
  任务提交时 confirmed=true 即人工确认，本 plan 预授权该场景。
