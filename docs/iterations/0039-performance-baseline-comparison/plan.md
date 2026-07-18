# ITER-0039 Performance Baseline Comparison

> 状态：Completed
> 日期：2026-07-15

## 背景

ITER-0038 已能稳定生成隐私最小化的聚合性能快照，但单张快照缺少参照。产品需要比较动态 Agent
任务前后的设备状态，同时不能把京东、抖音等应用流程固化成可失效的回放路径。

## 目标

- 定义两点性能比较 Input/Result Contract、单位、趋势和稳定阈值。
- 以两个已完成的 `device.performance.snapshot` TaskRun 为输入，校验设备、状态、顺序和证据。
- 计算 CPU、内存、电量、温度和 1 分钟负载的候选值减基线值。
- 在 Web 中支持“设为基线 → 选择另一快照 → 比较”，并提供 CLI。
- 明确两点快照只描述方向，不把相关性错误解释为因果或性能回退。

## 非目标

- 不执行、录制或回放被测应用的固定操作路径。
- 不自动将任意 Agent 任务包裹成前后采样 Workflow。
- 不做连续采样、时序图、告警、性能评分或自动回归判定。
- 不读取原始 Artifact、dumpsys、进程、应用或 PID 明细。
- 不新增 Adapter、Capability、Tool、Skill 或数据库表。

## Contract 兼容性

- 新增 Comparison Input/Result Schema 和 REST 端点，属于兼容性新增。
- 现有 Snapshot、TaskRun、Artifact 和数据库 Schema 不变，不需要迁移。
- 趋势是带阈值的方向描述，不表达“好/坏”；阈值作为结果字段公开，消费者不得隐藏其语义。

## 架构说明

比较是 Runtime Application 层的只读 Use Case。它只通过 TaskStore 读取两个 TaskRun，并调用无 I/O
的 Domain 比较函数；Interface 不直接读取数据库，Domain 不依赖 TaskStore，整个流程不访问设备或模型。
