# 文档与迭代规范

> 状态：Active  
> 更新日期：2026-07-03

## 1. 目标

保证人类和 Agent 能快速找到当前有效的信息，避免重复真源、过期方案和无法追踪的迭代决策。

## 2. 目录职责

```text
docs/
├── product/          长期有效的产品定位与方案
├── architecture/     当前有效的技术设计与架构边界
├── engineering/      开发、Contract、Skill、数据、测试、安全和协作规范
├── iterations/       每期迭代的计划、任务、验收和复盘
├── adr/              不覆盖历史的架构决策
├── releases/         对外或内部版本发布说明
└── archive/          已失效但需要保留的历史文档
```

根目录仅放：

- `README.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- 构建、许可证和仓库级配置

## 3. 单一真源

- 同一主题只能有一份 `Active` 文档。
- 其他文档引用真源，不复制长期维护的段落。
- 产品目标属于 `product/`，技术实现属于 `architecture/`，执行过程属于 `iterations/`。
- 架构决策进入 ADR；不能只留在聊天、提交信息或迭代笔记中。
- README 只提供摘要和导航。

## 4. 文档元数据

正式文档标题后至少包含：

```text
状态：Draft | Active | Superseded | Archived
更新日期：YYYY-MM-DD
```

需要时增加：

- 版本
- Owner
- 替代文档
- 关联迭代
- 关联 ADR

`Superseded` 文档必须说明由哪份文档替代。`Archived` 文档禁止继续追加当前设计。

## 5. 命名规范

- 文件和目录使用小写 kebab-case。
- ADR 使用 `NNNN-title.md`。
- 迭代使用 `NNNN-short-name/`。
- 发布记录使用语义版本或发布日期，例如 `v0.1.0.md`。
- 不使用 `final`、`new`、`latest`、`copy` 等无法长期理解的名称。

## 6. 迭代目录

每个迭代固定包含：

```text
NNNN-short-name/
├── plan.md
├── tasks.md
├── acceptance.md
└── retrospective.md
```

### `plan.md`

记录目标、背景、范围、非目标、依赖、风险和里程碑。

### `tasks.md`

记录可独立分配的任务。任务 ID 格式为 `TASK-NNNN-NN`，状态只使用：

- `todo`
- `in-progress`
- `blocked`
- `done`
- `cancelled`

同一任务同一时间只能有一个 Owner。并行 Agent 不得共同修改未声明的共享真源。

### `acceptance.md`

记录可执行或可观察的验收标准、验证命令、测试环境和证据要求。不能只写“功能正常”。

### `retrospective.md`

迭代开始时保持 Draft 模板；结束时记录实际交付、偏差、指标、问题和后续行动。完成后状态改为 Active 并冻结。

## 7. 迭代生命周期

```text
Proposed
→ Planned
→ Active
→ Verifying
→ Completed / Cancelled
```

- 同一时间原则上只有一个主要 `Active` 迭代。
- 进入 Active 前必须完成范围、任务和验收定义。
- 开发中新增范围必须先更新计划和任务，不以口头约定扩张。
- Completed 前必须更新验收结果和复盘。
- 长期有效的发现必须回写产品、架构、工程规范或 ADR。

## 8. 更新规则

- 小型澄清直接更新当前 Active 文档。
- 改变模块边界、安全模型、协议或核心技术选型时先新增 ADR。
- 改变产品范围时同时检查产品方案、技术方案和当前迭代。
- 文档迁移必须一次性修复全部仓库引用。
- 删除正式文档前先判断是否应移入 `archive/`。

## 9. Agent 工作要求

Agent 接任务时必须：

1. 读取当前迭代的 `plan.md`、`tasks.md` 和 `acceptance.md`。
2. 使用明确任务 ID 工作。
3. 只修改任务声明范围内的文档和代码。
4. 完成后更新任务状态、验证结果和必要文档。
5. 不把聊天内容当作项目长期记忆。

## 10. 文档评审清单

- 路径和分类是否正确？
- 是否与现有 Active 文档重复？
- 状态、日期和链接是否完整？
- 是否明确范围与非目标？
- 是否包含可验证的结果？
- 是否需要 ADR？
- 是否同步修复引用和索引？
