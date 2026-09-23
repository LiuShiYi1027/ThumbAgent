# ITER-0067 Real App Answer Baseline（真实 App 搜索并带回答案）

> 文档状态：Active
> 迭代状态：Completed
> 创建日期：2026-09-21
> 完成日期：2026-09-22
> 关联：[ITER-0061 复盘](../0061-agent-working-memory-and-results/retrospective.md)（驱动场景未交卷）· [ITER-0066 复盘](../0066-observation-empty-hierarchy/retrospective.md) · [ADR-0019](../../adr/0019-unicode-input-ime-helper.md)

## 背景

ITER-0061 交付了 scratchpad 与 finish `answer`，真机「关于手机带型号」证明内核链路
通，但驱动场景「真实 App 搜索并带回价格」两次都没交卷：一次输入未提交搜索，一次
空 dump 让模型空转。0066 已堵住空树空转。本迭代用可观察的第三方 App（夸克）把
「搜索 → 观察结果 → finish 带 answer」做成可重复基线。

本机荣耀京东停在登录页且 `FLAG_SECURE` 禁止截图，不作为本迭代验收场景。

## 目标

- **搜索可提交**：`input.unicode_text` 增加可选 `submit=search`。读回验证通过后、
  恢复原 IME 前，Runtime 发送固定 `keyevent 66`（KEYCODE_ENTER）。模型不能选择
  任意按键；Agent allowlist 不新增 Tool。
- **Unicode 不再截停循环**：`input.unicode_text` 成功后继续 Observe–Plan，才能在
  结果页 `finish` 带 answer。`settings.scroll_navigate` 终态语义不变。
- **Planner 会用**：prompt 与参数校验写明搜索类目标应带 `submit`；非法值在派发前
  拒绝，不切换 IME。
- **任务交卷**：Fake 覆盖「输入+提交 → 结果页 → finish 带 answer」。真机夸克场景
  `succeeded` + `planner_finish` + 非空 `result.answer`；价格正确性仍由人工核对
  （V1 不做数据自动断言）。

## 非目标

- 不绕过京东登录，不处理 `FLAG_SECURE` 新错误码（0066 可选跟进）。
- 不上 OCR、不扩 Agent Tool allowlist、不把 Enter 做成通用按键 Tool。
- 不自动断言价格数值。
- 不做 Desktop Skills 入口（ITER-0068）。
- 不改 Helper IME APK。

## 关键决策（已锁定）

1. **提交挂在 Unicode Skill 上，不新开 Capability**：搜索提交是「填完搜索框」的
   目标级收尾，与 ADR-0019 同一 Session/Lease/IME 恢复边界。固定 argv，与
   `navigation.home` 同类，不需要新 ADR。
2. **枚举只有 `search`**：后续 `done`/`go` 出现第二个真实场景再加。
3. **提交不可自动重试**：`unsafe`；读回成功后最多一次 Enter。
4. **驱动 App 是夸克**：本机可观察、0060 已验证中文输入；京东登录墙记限制。

## 兼容性

- `submit` 为可选字段，缺省行为与 0059/0060 完全一致。
- 结果契约可增加可选 `submitted`；旧结果仍合法。
- 无 SQLite 迁移。无破坏性 Contract。

## 风险与应对

- **Enter 在非搜索框上误提交表单**：仅 Skill 内部调用，且发生在已定位的可编辑
  目标读回成功之后；Agent 不能直接派发。
- **夸克用按钮而非 IME search**：模型仍可用 `tap_element` 点「搜索」；`submit`
  是主路径加速，不是唯一路径。
- **本地模型轮次不够**：真机预算 `max_rounds=12`、`deadline=900s`，失败保留报告。

## 测试与验收要点

- Fake：`submit=search` 在读回后、IME 恢复前发送 Enter；非法 submit 零设备动作。
- Agent：输入+提交后结果页 finish，`TaskRun.result.answer` 非空。
- 既有无 `submit` 的 Unicode 测试仍通过。
- 一次 `make check`；真机一条夸克带回答案。
