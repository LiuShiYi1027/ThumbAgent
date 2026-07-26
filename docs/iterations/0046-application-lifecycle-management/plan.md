# ITER-0046 Application Lifecycle Management

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-26

## 产品结果

外部 AI Agent 可以通过统一 MCP 能力检查一个已安装应用的运行状态，确定性启动和停止非系统应用，
并在两阶段明确确认后清除测试应用数据；每个动作都有异步状态、确定性后置验证和完整任务报告。

## 范围

- 新增有界应用运行状态：进程是否存在、是否前台、package stopped flag。
- 将已有 `app.open` 接入异步任务和 MCP 目标级入口。
- 新增受 Medium 风险确认保护的非系统应用强制停止。
- 新增 High 风险应用数据清除 Prepare/Submit 协议。
- Android 只使用固定参数；REST、MCP 不暴露 Shell 或任意 ADB 参数。
- 迭代末集中运行完整门禁和一套真机 E2E Suite。

## 非目标

- 不授予、撤销或枚举应用权限。
- 不操作系统应用，不批量处理应用。
- 不读取、备份或证明应用私有数据内容。
- 不精确枚举后台 Service，不承诺进程存在等同业务运行。
- 不扩展 iOS、鸿蒙或多设备调度。

## 风险与兼容性

- 状态检查和启动为 Low；停止为 Medium；清除数据为 High。
- 清除数据复用已接受的短期、单次、范围绑定 High 风险授权模型，Approval 独立绑定设备、包名、
  版本和数据删除语义；不改变 Policy 信任边界，因此不新增 ADR。
- 新增 Contract、Capability、Task 类型、REST 和 MCP Tool，属于兼容性新增，无需数据库迁移。

## 预算

- 6 个 Task，目标 2–3 个工作日。
- 开发阶段只运行 focused tests；候选稳定后运行一次完整 `make check`。
- 真机 E2E 集中验证状态、启动、停止和清除数据；高风险阶段单独展示影响摘要并等待用户确认。
