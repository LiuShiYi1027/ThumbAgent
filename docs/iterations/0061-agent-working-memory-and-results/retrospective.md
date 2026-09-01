# ITER-0061 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-01

## 实际交付

- **契约**（7daeb98）：`AgentDecision +scratchpad`（可选、1024 上限、缺省=不更新/
  空串=清空）、finish 携带 `answer`（1-2000）、`TaskRun +result`；TS 生成类型同步，
  12 条契约/双语言一致性测试。
- **Runner/Provider 接线**（b0c7033）：scratchpad 任务级状态机随下轮观察摘要注入
  prompt；finish answer 持久化进 `TaskRun.result`；报告 CLI Answer 行透出；
  system prompt 写入记忆语义与敏感内容禁令。
- **E2E 场景入库**（020ff2f、4941f33）：京东/夸克查价 preset + 确定性「关于手机
  带型号」场景（后者同时是捷径守卫的活体探针）。
- **审查驱动的内核加固**（本迭代窗口内的深度审查后续修复，直接服务本迭代承诺）：
  - 捷径守卫（18c3e25，M6）：目标含结果类谓词（带回/告诉/价格/…）时导航捷径
    让位给模型循环——修复捷径截胡 answer 场景的直接冲突。
  - Runner 可靠性（18c3e25，M1/M2/M3）：NO_PROGRESS 耗尽不再复用旧 step_id；
    轮次预算 `MAX_AGENT_ROUNDS=12` 唯一真源（删除 Planner 第 7 轮硬拒、
    evaluator 50→12、Schema 上限对齐）；捷径与 RUN_SKILL 验收观察接入瞬时重试。
  - Desktop 透出补齐（a7471ad）：报告页渲染 `report.result.answer`，plan 的
    「CLI / REST / Desktop 透出」承诺至此完整。

## 验证结果

- 集中全量验证：`make check` 563 tests OK（迭代窗口内 517→563），类型/格式/
  TS Contract 同步检查全部通过；Rust 侧 cargo test 25/25。
- 真机验收（2026-09-01，MagicOS BKQ-AN10，LM Studio `qwen3.8-27b-uncensored-mlx`
  text 模式）：
  - **answer 带回主验收通过**：「打开关于手机页面，把设备型号带回来」4 轮
    succeeded（357s），`completion_source=planner_finish`，`answer=BKQ-AN10`
    与 `getprop ro.product.model` 逐字符一致。捷径未触发（谓词守卫生效）。
  - **scratchpad 跨轮记忆实证**：夸克查价任务中模型 8 轮持续维护准确工作记忆
    （记录已尝试动作与其效果），注入/更新链路工作正常。
  - **暂停/恢复真机链路**（REST 路径，桌面按钮同款端点）：queued → running →
    pause_requested → paused（边界生效 ~10s，暂停期设备前台零变化）→ resumed →
    cancel_requested → cancelled，事件流逐条正确。
  - 京东驱动场景未通过（见偏差），按 plan 非目标声明转后续观察。

## 偏差与限制

- **驱动场景替换**：plan 原驱动场景「京东搜索 iPhone 17 带回价格」两次尝试均未
  到达 finish——第一次 round 3 起模型 TTFT 连续超 120s（MODEL_UNAVAILABLE），
  第二次模型把 unicode 输入打到不可编辑节点（TARGET_NOT_EDITABLE）。夸克等价
  场景一次读回误报失败（TEXT_INPUT_NOT_VERIFIED，事后 dump 证明文本完整在场，
  属读回时机缺口）、一次 8 轮 NO_PROGRESS（搜索始终未真正提交）。内核验收改由
  确定性「关于手机」场景完成：scratchpad 与 answer 的契约—Runner—Provider—报告
  链路得到端到端证明，但「真实查价」类长链路意图的模型层可靠性未在本迭代证明。
- **真机暴露的四个跟进项**（详见后续行动）：权限弹窗自主点击、unicode 读回时机、
  queued 任务不可暂停、阻塞式模型调用期间暂停/取消不生效。
- **模型环境约束**：本地推理模型 TTFT 间歇超过 Provider 校验允许的 120s 上限；
  answer 正确性按 V1 语义由人工核对，不做数据自动断言。

## 效率指标

- 迭代窗口：2026-08-31 → 2026-09-01（含穿插的深度审查与三批修复）。
- 内核验收真机运行：约 6 次任务执行（京东×3、夸克×2、关于手机×1、暂停链路×2），
  终态 succeeded 1 次；失败全部产生可解释报告，无误报成功。

## 后续行动

1. **权限弹窗风险升级（建议下一迭代优先）**：模型在 Quark 录音权限弹窗上自主
   点击「仅使用期间允许」——语义点击作为通用低/中风险动作绕过了权限类 High
   风险边界。建议：前台为 permissioncontroller 时提升 tap 风险等级并要求确认。
2. **unicode 输入读回健壮性**：读回发生在页面跳转间隙时误判失败，需 settle
   后重定位或有界重读（真实文本已在场）。
3. **queued 任务暂停语义**：排队中任务请求暂停返回 TASK_STATE_CONFLICT，只能
   取消；需明确设计（排队可暂停 or 文档化现状）。
4. **阻塞式模型调用（M4）**：Provider decide 同步阻塞，取消/暂停/deadline 在
   调用期间失效（真机实测取消延迟一个轮次）；建议传输层移入 `asyncio.to_thread`
   并轮询控制探针。
5. **京东搜索结果页 Observation**：uiautomator dump 持续空节点问题（小米实测，
   本窗口荣耀未复现但模型未走到）留观察项；真实比价链路验收推迟到模型层
   可靠性提升后。
6. **遗留 backlog**：M5 捷径副作用证据、M14 Keychain FFI、Web UI 稳定幂等键。
