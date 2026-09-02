# ADR-0021: 声明式复合 Skill DSL 与 Skill Registry 持久化

- Status: Accepted
- Date: 2026-09-01（2026-09-01 经项目负责人确认方向）
- Deciders: Mobile Agent Team

## Context

当前 Skill 体系（ADR-0002）的全部 15 个 Skill 是硬编码 Python 类，在
`RuntimeService.__init__` 手工装配；`skills/manifests/*.json` 只被契约测试引用，
运行时不加载；REST 的 skill invoke 路由逐条硬编码正则。产品文档定义的
「Skill = 目标级能力，Manifest 声明与执行代码分离」目前只有前半成立。

路线图 §4.4 把「Skill 扩展与管理」列为 V2 平台元能力，首驱动场景是应用稳定性
测试（`app.stability_test`）：时间盒内确定性遍历交互 + 崩溃/ANR 判定 + 性能曲线
采样 + 结构化报告——它是纯编排，不需要新设备原语，但超出一个 Python 函数合理
承载的声明式结构。真实需求量化依据：约 65% 客户端测试场景可由声明式 Skill 层
覆盖（testing-scenario-coverage.md）。

核心矛盾：用户/第三方需要自定义复合技能，但 `security.md` 与 ADR-0002 禁止任意
执行代码进入 Runtime。唯一可行形态是**声明式 DSL 由 Runtime 解释执行**。

## Decision

### 执行边界（不信任 DSL 的内容，只信任解释器）

1. DSL 是纯数据文档（JSON，Contract Schema 定义在 `contracts/schemas/`），
   不包含任何可执行代码、表达式求值或外部引用。
2. 解释器只能引用**已登记**的 Tool/Capability；每一步仍走既有
   `ToolRuntime.execute` 管线——Schema 校验、Capability 校验、Policy 授权、
   前置/后置 Observation 一层不少。DSL 不产生任何新的设备访问路径。
3. DSL 的控制流受限：顺序步骤、有界时间盒循环（`max_duration_seconds` +
   `max_iterations` 双上限）、有界条件分支（条件只能引用上一步结构化结果的
   枚举字段，不做任意表达式）。无递归、无子 Skill 调用（V1 不允许组合嵌套）。
4. 复合 Skill 的风险等级 = 所编排能力的最高风险等级，确认语义取各能力的并集；
   DSL 文档不得声明低于派生值的风险等级（解释器强制取 max，不信任文档声明）。
5. 每一步的设备写动作仍绑定任务级 `device_id`；DSL 不得改变目标设备。

### 管理边界（Registry 从启动期装配改为持久化运行时状态）

6. 内置 Skill 保持硬编码受信代码，不可被 DSL 覆盖或禁用（防止管理面被用于
   削弱内置安全语义）。
7. 自定义 Skill 持久化到 SQLite（新迁移）：`skill_id + version` 联合主键、
   DSL 文档、派生风险等级、enabled 状态、创建/更新/启停时间、来源标识。
   版本不可变——更新即新增版本，历史版本保留用于审计与复现。
8. 管理面（REST）：注册（需 confirmed）、查看、启停、版本列表、删除
   （仅自定义、保留审计事件）。MCP 只读暴露已启用 Skill 清单；Desktop
   管理页属后续 Task。
9. 注册即审计：`skill.registered / skill.enabled / skill.disabled /
   skill.deleted` 进入事件流，payload 含 DSL 文档 SHA-256 而非原文。
10. 任务报告记录执行所用 `skill_id@version`，保证可复现。

### 首驱动场景

`app.stability_test` 作为首个官方 DSL 复合 Skill 交付：参数为目标 app_id +
时间盒 + 动作频次上限；编排 `app.open`、确定性遍历（tap/swipe 有界集合）、
周期性 `performance.snapshot` 采样、结束时 `logs.collect` 崩溃/ANR 判定，
输出结构化报告。派生风险 Medium（最高组件风险）。

## Consequences

- 客户端测试场景的 ~65% 可由声明式层覆盖，无需为新组合逐个发版 Runtime。
- 解释器是唯一新增信任面：DSL 校验、步骤边界、循环上限的正确性成为安全
  关键代码，需要完整的负向测试矩阵（未知工具、越界参数、超上限循环、
  嵌套调用、风险降级声明）。
- SQLite 新增表需要数据迁移；Runtime 重启后自定义 Skill 状态可恢复。
- REST 技能路由从硬编码正则改为「内置白名单 + Registry 查询」两阶段，
  未知 skill_id 返回 RESOURCE_NOT_FOUND。
- 不做：第三方签名 Skill 包、远程 Skill 仓库、DSL 子技能嵌套、任意表达式
  求值。这些属于明确的未来非目标。

## Alternatives Considered

- **保持硬编码，每个复合 Skill 写 Python**：65% 场景覆盖意味着持续的 Runtime
  发版负担，且用户无法自定义。否决。
- **允许签名第三方代码包**：签名/验收基础设施成本高，且执行边界从「数据」
  变成「代码」，安全评审面大一个数量级。V2 不做。
- **用 Agent 循环替代 DSL**（模型多轮规划完成复合任务）：已存在的路径，但
  稳定性测试等场景要求确定性遍历与固定采样节奏，模型规划不保证可复现；
  DSL 与 Agent 互补——DSL 管确定性编排，Agent 管开放式目标。

## Follow-up

- ITER-0062 落地本 ADR：DSL Contract Schema → 解释器 → Registry 持久化与
  管理面 → `app.stability_test` 真机验收。
- DSL 表达能力按真实需求拉动扩充；每新增一种控制流构造需重新审视执行边界。
