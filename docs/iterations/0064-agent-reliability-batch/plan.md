# ITER-0064 Agent Reliability Batch（Agent 可靠性批次）

> 文档状态：Draft
> 迭代状态：Planned
> 创建日期：2026-09-02
> 关联：[深度审查发现](../..)（session 2026-09-01）· [ITER-0061 复盘](../0061-agent-working-memory-and-results/retrospective.md)（跟进项 2/3/4/6）· [可靠性模型](../../architecture/reliability-model.md)

## 背景

深度审查与 ITER-0061/0063 真机验收暴露了五个「既有承诺在边界条件下不成立」
的存量缺陷，每一项都有真实复现证据。本迭代集中收口，不引入新能力、新边界或
Contract 语义变更。

## 目标

- **M4 阻塞式模型调用**：Provider decide 移出事件循环（`asyncio.to_thread`），
  等待期间轮询取消/暂停/deadline 探针；取消即放弃等待（线程无设备副作用，
  自然超时），不再出现「取消后还等一个轮次」。
- **unicode 读回时机**：注入后读回遇节点缺席（match_count=0/actual null）时
  settle 后有界重读一次；与真正的内容不一致（tamper，不重试）区分开。
- **queued 任务可暂停**：queued → paused → resumed 回 queued；执行器取任务前
  检查暂停标志。暂停排队任务不需要轮次边界（本就没有在跑）。
- **M5 捷径副作用证据**：导航捷径执行成功即先落盘 shortcut_step，再验收；
  验收失败回退模型主循环继续，而非终结任务——报告不再丢失已发生的设备副作用。
- **Web UI 幂等键**：内嵌 Web UI 与 MCP/CLI 对齐，从「端点+规范化参数」派生
  稳定键（复用 api/idempotency.py 的规范化逻辑；Web UI 是纯前端，用同源算法
  在 JS 侧实现并断言与服务端派生一致）。

## 非目标

- 不改 Provider 传输协议/超时语义；不引入 aiohttp 等新依赖（to_thread 即可）。
- 不改暂停的轮次边界语义（running 任务仍在边界生效）。
- 不做崩溃/ANR 自动判定、不做呈现层（ITER-0065 候选）。
- 不重设计 DSL/Registry（刚交付）。

## 兼容性

全部为实现层修复：无 Contract 变更、无 Schema 变更、无迁移。既有测试不得回归。

## 风险与应对

- **M4 动执行器线程模型**：放弃等待的线程仍持有 urllib 连接——确认其无设备
  副作用、无共享状态写入；测试断言取消后任务终态正确且线程结果不落地。
- **queued 暂停的状态机面**：ExecutionStatus 转换表新增 queued→paused→queued；
  Runtime 重启恢复路径（paused 以 TASK_INTERRUPTED 失败）覆盖 queued-paused。
- **unicode 重读的幂等性**：重读只发生在「节点缺席」，内容不一致仍立即失败，
  不引入重复输入风险（重读是只读操作）。

## 测试与验收要点

- 每项先写复现测试（审查报告已有精确复现路径）。
- M4：取消在模型调用进行中生效（<2s 响应），deadline 在调用期间到期即终止。
- unicode：节点缺席误报场景修复前后对比；tamper 场景不重读。
- queued 暂停：queued→paused→queued→running 全链路 + 重启恢复。
- M5：捷径验收失败任务不回退前报告含 shortcut_step；回退后模型循环继续。
- 真机集中验收：暂停/取消延迟测量 + unicode 中文输入场景回归。
