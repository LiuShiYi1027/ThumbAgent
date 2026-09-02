# ITER-0062 Declarative Skill DSL & Registry（声明式复合 Skill 与注册表管理面）

> 文档状态：Final
> 迭代状态：Completed
> 创建日期：2026-09-01
> 完成日期：2026-09-02
> 关联：[能力路线图 §4.4](../../product/capability-roadmap.md) · [ADR-0021](../../adr/0021-declarative-skill-dsl-registry.md)（Accepted，2026-09-01 负责人确认方向）· [ADR-0002](../../adr/0002-tool-skill-model.md) · [ITER-0061 复盘](../0061-agent-working-memory-and-results/retrospective.md)

## 背景

Skill 声明与执行分离目前只有一半：15 个内置 Skill 全是硬编码 Python 类，
manifest JSON 仅供契约测试引用，REST 路由逐条硬编码。路线图 §4.4 将
「Skill 扩展与管理」列为 V2 平台元能力，依赖 ITER-0061 已交付的
scratchpad/result 契约；约 65% 客户端测试场景可由声明式 Skill 层覆盖
（testing-scenario-coverage.md）。

## 目标

- **DSL Contract**：`skill-dsl.schema.json` 定义声明式复合 Skill 文档——顺序
  步骤、有界时间盒循环、有界条件分支；只引用已登记 Tool/Capability；无代码、
  无任意表达式。
- **解释器**：Runtime 解释执行 DSL，每一步走既有 ToolRuntime 管线（Schema /
  Capability / Policy / 前后观察）；派生风险取组件最大值，不信任文档声明；
  完整负向测试矩阵。
- **Registry 持久化与管理面**：SQLite 存储自定义 Skill（版本不可变、启停、
  审计事件）；REST 管理面（注册需 confirmed、查看、启停、版本、删除）；
  内置 Skill 不可被覆盖/禁用。
- **首驱动场景**：`app.stability_test` 官方 DSL Skill——时间盒内确定性遍历 +
  性能采样 + 崩溃/ANR 判定 + 结构化报告，真机验收。

## 非目标

- 不做第三方签名 Skill 包、远程仓库、DSL 子技能嵌套、任意表达式求值。
- 不做 Desktop 管理页（后续迭代；本迭代 REST + 事件流即可管理）。
- 不做 MCP 自定义 Skill 调用（MCP 只读暴露清单；调用面扩大待真实需求）。
- 不改内置 Skill 的实现与装配方式。
- DSL Skill 内不调用 Agent 循环（确定性编排与模型规划互补，不混层）。

## 关键决策点（已在 ADR-0021 陈述倾向，实施前需负责人确认方向）

- DSL 控制流上限：顺序 + 时间盒循环 + 枚举字段条件分支，三件套够覆盖
  稳定性测试与盘点场景；更强表达力留给真实需求拉动。
- 风险派生强制 max：DSL 文档的风险声明仅作展示，解释器以组件能力派生为准。
- 版本不可变：更新 = 新版本，任务报告记录 `skill_id@version` 保证可复现。

## 兼容性

- 新增 REST 端点（/v1/skills 管理面）与新任务类型，不改既有端点语义。
- SQLite 新迁移（skills 表 + 审计事件）；不改既有表结构。
- 内置 Skill 的契约、路由、行为全部不变；回归测试必须全绿。

## 风险与应对

- **解释器是新信任面**：DSL 校验/步骤边界/循环上限错误等于绕过执行边界。
  应对：负向测试矩阵（未知工具、越界参数、超上限、嵌套、风险降级声明）
  作为验收硬条件。
- **管理面被用于削弱安全语义**：内置 Skill 不可覆盖/禁用；注册与启停全部
  审计；DSL 文档哈希入事件，原文只在本地存储。
- **范围膨胀**：DSL 表达能力每加一种构造都要重审执行边界——本迭代只实现
  三件套，评审粒度保持小。

## 测试与验收要点

- Contract：DSL Schema 正/负样本、生成类型同步、风险派生规则测试。
- 解释器：单测覆盖执行顺序、时间盒双上限、条件分支、组件失败传播、
  每步 Policy/Capability 强制（用 Fake Adapter + 拒绝路径断言）。
- Registry：迁移、版本不可变、启停状态恢复、审计事件、内置保护。
- REST 管理面：注册 confirmed 门、未知 id 404、内置覆盖拒绝。
- 真机 E2E：`app.stability_test` 对单个第三方应用跑 2 分钟时间盒，
  报告含动作计数、性能采样序列、崩溃/ANR 判定（显式标记）。
