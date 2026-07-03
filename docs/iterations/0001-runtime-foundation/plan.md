# ITER-0001: Runtime Foundation

> 状态：Completed  
> 更新日期：2026-07-03  
> Owner：Codex

## 目标

建立 Mobile Agent 的可运行工程骨架，完成 Contract、Python Runtime 健康检查、Android ADB Runner 和设备发现，为后续 Observation 与 Skills 提供稳定基础。

## 范围

- Monorepo 基础目录和统一开发命令
- Python Runtime 包与健康检查 API
- 核心 Device Contract
- Device Adapter 抽象
- 受控 ADB Runner
- Android 设备发现和基础信息
- Fake Adapter / Fake Process Runner
- 单元、Contract 和无设备集成测试
- 本地开发说明

## 非目标

- 桌面工作台完整界面
- 截图、UI 树和输入动作
- Agent Loop 与模型接入
- Skills/MCP 正式实现
- 数据库任务状态机
- iOS、鸿蒙 Adapter
- 多设备并发任务

## 依赖

- Python 3.11+
- Android Platform Tools（仅真实设备手工验证需要）
- 当前 Accepted ADR

## 风险

- 开发机没有 ADB 时，默认测试仍必须可运行。
- 不同 ADB 版本输出可能存在差异，需要 fixture 驱动解析测试。
- Contract 过早复杂化会拖慢首个闭环，V1 只定义当前需要字段。

## 里程碑

1. 工程骨架和统一命令可运行。
2. Runtime 健康检查通过。
3. Fake Adapter 能返回稳定 Device Contract。
4. Android Adapter 能解析 `adb devices -l`。
5. 无设备测试集和可选真实设备验证通过。

## 完成条件

以 [acceptance.md](./acceptance.md) 全部必选项通过、任务完成并提交复盘为准。
