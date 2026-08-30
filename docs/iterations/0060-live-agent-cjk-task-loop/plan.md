# ITER-0060 Live Agent CJK Task Loop（真机模型驱动中文任务闭环）

> 文档状态：Final
> 迭代状态：Completed
> 创建日期：2026-08-30（快速通道执行，收尾补记；执行窗口 2026-08-25 → 2026-08-30）
> 完成日期：2026-08-30
> 关联：[ITER-0059](../0059-unicode-text-input/plan.md) 复盘保留项 · [ADR-0019](../../adr/0019-unicode-input-ime-helper.md) · [能力路线图](../../product/capability-roadmap.md)

## 背景

ITER-0058/0059 交付了混合动作空间第一波与 `input.unicode@1` 中文输入能力，
但二者都在确定性脚本与 Fake 集成层验证；0059 复盘明确保留：「自然语言中文任务的
真机模型循环未在 E2E 中重复执行」。

同时，本地自部署推理服务（LM Studio，OpenAI 兼容）接入后暴露两处兼容问题：
`response_format` 不被部分本地服务支持、本地 CV 模型可能产出退化 bounds。
这两项不解决，「真实模型 + 真实设备 + 中文任务」的完整闭环无法在线验证。

说明：本迭代各变更单独看均满足快速通道条件（单个修复/兼容新增/测试补充），
实际按快速通道执行；因组合交付了一个可验证的产品结果，收尾时补建迭代文档，
满足记录、复盘与提交边界要求。

## 目标

- 本地 OpenAI 兼容推理服务可用：`response_format` 可配置（本地服务降级为 text），
  解析器容忍退化 bounds 不静默崩溃。
- 打通真机模型驱动中文任务闭环：自然语言目标 → 模型规划 → 启动应用 →
  定位搜索框 → `input.unicode_text` 技能在线调用 → runtime acceptance 验收。
- 新增 hint 选择器策略：空输入框 text 为空，此前无法被 text 策略定位；
  占位提示（hint）是唯一稳定锚点，需在 Contract、Locator、Observation 摘要与
  Planner prompt 四层同时暴露，模型才能自主选用。
- 真机模型驱动场景入库为显式 E2E Suite，可重复执行，不进默认快速测试集。

## 非目标

- 不做模型评测、选型或横向对比（模型只是当前环境的可替换依赖）。
- 不做证书弹窗等系统对话框的自动处理策略（暂缓，模型自行处理已够用）。
- 不解决敏感词子串误报（"iPhone" 命中 "phone" 形态，待产品拍板）。
- 不做任务中断恢复/证据落盘（识别为候选需求，见复盘）。
- iOS、多设备、任意 shell 等 V1 排除项不变。

## 兼容性

- Selector 新增 `hint` 策略：向后兼容的 Contract 新增字段，按 §9 不自动要求 ADR；
  TS 类型经 `generate_ts_contracts.py` 再生成同步。
- Provider 配置新增 `response_format` 可选项，默认行为不变。
- 无持久化迁移、无安全信任边界变化。

## 风险与应对

- **hint 命中多节点**：占位文本可能被页面多个节点共享 → 显式 TARGET_AMBIGUOUS
  报错，由调用方收紧选择器（真机实测发生一次，根因为验收选择器而非定位缺陷，
  详见复盘）。
- **模型输出不可信**：沿用既有决策校验与 repair 链路；本地模型契约违约时
  返回 MODEL_OUTPUT_INVALID，不产生设备副作用。
- **本地服务延迟不可控**：单轮 13–87s 波动，E2E 脚本提供 `--rounds`/`--deadline`
  预算控制；超时语义为 TASK_DEADLINE_EXCEEDED，不算能力失败。

## 测试与验收要点

- hint 策略：Contract 测试 + Locator 单测 + Observation 摘要暴露断言。
- 集中一次 `make check` 全量通过。
- 真机验收场景：夸克「打开浏览器 → 搜索框输入你好」，模型全程在线规划，
  验收唯一命中输入后的 EditText；unicode 输入后 IME 正确恢复。
