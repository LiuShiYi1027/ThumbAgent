# ITER-0062 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-02

## 实际交付

- **ADR-0021（Accepted）**：声明式 DSL 双重信任边界——纯数据文档、解释器只引用
  已登记 Tool/Capability、风险强制派生 max、版本不可变、全程审计。
- **DSL Contract**（307f4cf）：`skill-dsl.schema.json` 三件套控制流（顺序 /
  时间盒双上限循环 / status 条件分支），控制体只含工具步骤；Python 解析器
  同界强制；TS 类型生成。
- **解释器**（17f5706）：preflight（输入绑定/$inputs 引用/注册检查/派生风险
  策略门）先于任何设备动作；顶层失败中止、loop 体内失败记录后继续；
  step_boundary/on_step 探针钩子。
- **Registry 持久化**（17f5706）：custom_skills 表（迁移 0003）、版本不可变、
  semver 最新解析、内置 id 保护、审计回调。
- **管理面 + 任务类型**（7de1ba6）：REST 注册（confirmed 门）/清单/详情/启停/
  删除/审计端点；skill_audit 表（迁移 0004，payload 只含哈希）；异步任务类型
  `skill.dsl.run`（ADR-0013 注册模式），goal 记录 `skill_id@version`，步骤边界
  取消/暂停/deadline 探针。
- **官方 DSL Skill**（f0d3a3c、dc23ca5）：`app.stability_test` 文档 +
  Runtime 装配时幂等自动加载（不覆盖用户启停状态）。

## 验证结果

- 集中全量验证：646→651 tests OK，契约/类型/格式/TS 同步全过。
- 真机（2026-09-02，MagicOS BKQ-AN10）：
  - 管理面全链路：注册 → 清单 → 详情 → 禁用（调用被 SKILL_DISABLED 拒）→
    启用 → 审计序列完整（只含哈希）。
  - 短变体 `app.stability_smoke`（4 迭代）：succeeded，12 步记录、
    `document_sha256` 入证据摘要、设备回到目标应用前台。
  - 官方文档 75s deadline：timed_out 干净终止，11 步证据保留。
  - Runtime 重启：rest 来源自定义技能保留、builtin-dsl 自动加载、
    用户启停状态不丢。

## 偏差与限制

- **性能采样缺失**：所有观察类工具（performance.capture、logs.capture 等）均为
  `direct_invocation=False` 的 Skill 中介工具，DSL 步骤无法引用。稳定性测试的
  性能曲线采样与崩溃/ANR 判定因此未覆盖；证据暂由每步前后 Observation 承担。
  这是 DSL 表达边界与 Tool 分层（ADR-0002）的真实张力，不是实现疏漏。
- **DSL 不支持输入绑定到循环上限**：`duration_seconds`/`max_actions` 输入只做
  preflight 预算校验，实际时间盒由任务 deadline 控制；文档内固定 600s/200 次
  双上限作绝对天花板。
- **DSL 不能调用 Skill/子技能**（ADR-0021 明确排除嵌套）：上述观察能力缺口
  的最自然解法（允许引用启用中的目标级 Skill）需要重新评审执行边界。
- A6 以短变体 + 有界运行替代完整 2 分钟时间盒验收；机制证据完整，长时稳定性
  行为（发热、内存爬升下的 ROM 表现）未测量。

## 效率指标

- 迭代窗口：2026-09-01 → 2026-09-02（立项到关闭约 1 个工作日，4 个实现波次）。
- 提交：6 个 feature 提交 + 1 个立项提交；测试净增 73 条（578→651）。
- 真机运行：3 次 DSL 任务（1 次设备掉线正确失败、1 次 succeeded、1 次
  timed_out），全部产生可解释报告。

## 后续行动

1. **DSL 观察能力缺口（建议下一迭代）**：允许 DSL 步骤引用已启用的目标级
   Skill（仅内置、仅观察类白名单），恢复稳定性测试的性能采样与崩溃判定；
   需更新 ADR-0021 执行边界条款并重审风险派生。
2. **Desktop 管理页**：自定义 Skill 的查看/启停在桌面端呈现（REST 已就绪）。
3. **MCP 只读清单**：自定义 Skill 清单对 MCP 暴露（ADR-0021 决策 8 的
   MCP 部分未实施）。
4. **长时稳定性行为测量**：完整 2 分钟+ 时间盒在充电/控温条件下执行并记录。
