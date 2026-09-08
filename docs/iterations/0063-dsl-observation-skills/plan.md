# ITER-0063 DSL Observation Skills（DSL 观察能力 + 稳定性测试完整化）

> 文档状态：Draft
> 迭代状态：Planned
> 创建日期：2026-09-02
> 关联：[ADR-0021 修订](../../adr/0021-declarative-skill-dsl-registry.md) · [ITER-0062 复盘（跟进项 1/4）](../0062-declarative-skill-dsl/retrospective.md) · [能力路线图 §4.4](../../product/capability-roadmap.md)

## 背景

ITER-0062 真机验收暴露 DSL 表达边界的真实缺口：所有观察类工具都是
`direct_invocation=False` 的 Skill 中介，DSL 步骤无法引用，`app.stability_test`
因此缺性能曲线采样与崩溃/ANR 判定——而这恰是稳定性测试的核心产出。0062 复盘
跟进项 1 建议：允许 DSL 步骤引用观察类内置 Skill 白名单，并重审执行边界。

## 目标

- **ADR-0021 修订**：执行边界增加「Skill 级引用」条款——仅限白名单内的内置
  观察类 Skill（`device.performance.snapshot`、`device.logs.collect`），
  不开放自定义 Skill 嵌套、不开放写类 Skill。
- **DSL Contract 扩展**：`skill_step` 步骤类型（兼容性新增）；循环/分支体
  允许工具步骤与 Skill 引用步骤。
- **解释器**：Skill 引用经白名单 + 注入的 skill_invoker 执行，派生风险取
  组件（工具 + 被引用 Skill）最大值；无 invoker 时 preflight 拒绝。
- **稳定性测试完整化**：`app.stability_test` 1.1.0——循环内性能采样 +
  结束时日志崩溃/ANR 判定；完整时间盒真机验收。

## 非目标

- 不开放自定义 Skill 互相嵌套、不开放写类 Skill 引用、不做条件表达式扩展。
- 不改 DSL 既有步骤语义；1.0.0 文档行为不变（版本不可变，走 1.1.0 新版本）。
- 不做 Desktop 管理页与 MCP 清单（沿用 0062 跟进项，另行排期）。

## 关键决策点

- Skill 引用白名单是编译期常量（代码内），不接受 DSL 文档或 REST 传入扩展。
- 被引用 Skill 的确认语义并入派生风险：观察类 Skill 为 Medium，含其引用的
  文档派生风险至少 MEDIUM。
- `app.stability_test` 1.0.0 保持原样可运行；1.1.0 是新版本（版本不可变原则）。

## 兼容性

- Schema 兼容性新增（新 $def + oneOf 成员），按 contract-versioning.md 流程。
- 既有 DSL 文档、管理面端点、任务类型行为不变。

## 风险与应对

- **Skill 级引用扩大信任面**：白名单常量 + preflight 拒绝 + 负向测试钉死
  （非白名单 Skill、写类 Skill、自定义 Skill 引用全部拒绝）。
- **采样噪声影响被测应用**：采样频次由循环节奏自然限制（每迭代一次），
  文档注明；不做额外节流机制。

## 测试与验收要点

- Contract：skill_step 正负样本、oneOf 成员断言、生成类型同步。
- 解释器：白名单强制、invoker 缺失拒绝、风险派生含 Skill 组件、循环内采样。
- 真机 E2E：`app.stability_test@1.1.0` 对第三方应用完整时间盒（≥2 分钟），
  报告含性能采样序列与崩溃/ANR 判定（显式标记）。
