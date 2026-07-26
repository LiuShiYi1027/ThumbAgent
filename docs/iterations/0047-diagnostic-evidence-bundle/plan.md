# ITER-0047 Diagnostic Evidence Bundle

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-26

## 产品结果

用户或外部 AI Agent 通过一次受确认的异步调用，采集设备当前截图、UI Tree、脱敏日志、聚合性能、
前台应用和可选目标应用状态，并获得有完整性清单的本地诊断包与统一任务报告。

## 范围

- 新增 `device.diagnostics.bundle@1` Medium 风险确定性能力。
- 诊断包内容固定、大小有界、全部本地保存，包含 SHA-256 Manifest。
- 复用现有 Observation、日志、性能和应用状态能力，共用 Task Session 与 Lease。
- 接入异步 Task、REST、MCP、CLI/Web 报告和真机验收。

## 非目标

- 不实时流式采集、录屏或持续监控。
- 不增加进程级性能、Crash/ANR 根因分析或任意 Shell。
- 不上传、外发或开放通用 Artifact 下载接口。
- 不实现 iOS、鸿蒙或多设备并发。

## 风险与兼容性

诊断包读取截图、UI Tree 和日志，风险为 Medium，必须显式确认。新增 Contract、Capability、
Task 类型、Artifact 枚举、REST 与 MCP Tool，均为兼容性新增；不改变信任模型或依赖方向，
不需要 ADR 或数据库迁移。

## 预算

- 5 个 Task，目标 1–3 个工作日。
- 开发阶段运行 focused tests；候选稳定后运行一次完整 `make check`。
- 迭代末集中执行一次真机诊断包 E2E。
