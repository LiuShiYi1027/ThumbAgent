# ITER-0040 MCP Skills Developer Preview

> 状态：Completed
> 日期：2026-07-18

## 背景

Runtime 已具备动态 Agent、任务、日志、性能和报告能力，但主要通过 Web/CLI 使用。为了兑现
AI-native Skills 产品形态，需要让外部 Agent 通过标准协议发现并调用目标级能力。

## 目标

- 提供兼容 MCP `2025-11-25` 的 stdio Server 和完整初始化生命周期。
- 通过固定 localhost REST API 复用现有 Runtime，不创建第二个设备执行内核。
- 暴露设备就绪、设备列表/检查、Agent 提交、任务列表/状态/报告/取消、日志、性能和比较能力。
- 所有耗时设备能力使用现有异步 TaskExecution，MCP 调用立即返回 task_id。
- 提供 Contract、严格验证、限流、安全错误、配置示例、集成测试和本地 E2E。

## 非目标

- 不暴露 ADB、任意 Shell、底层 input Tool 或动态 Handler。
- 不实现 MCP Streamable HTTP、Resources、Prompts、Sampling 或实验性 MCP Tasks。
- 不允许 MCP 直接读取数据库、Artifact 文件或密钥文件。
- 不新增 iOS/鸿蒙 Adapter、包安装卸载或多设备调度。

## Contract 兼容性

- 新增 MCP Tool Input Schema 和 stdio Interface，属于兼容性新增。
- 现有 REST、Task、Skill、Artifact 和数据库 Contract 不变，不需要迁移。
- MCP Tool 名称进入 Preview 稳定面；改变输入必填项、确认或副作用语义需要按 Contract 规范演进。

## 架构说明

MCP 与 CLI 一样是 Runtime API Consumer：`MCP -> localhost REST -> Application -> Device Gateway`。
它不作为内部模块总线。协议和信任边界详见 ADR-0015。
