# 架构边界规范

> 状态：Active
> 更新日期：2026-07-03

## 1. 分层

```text
Interface → Application → Domain → Device Gateway → Adapter
```

横切模块 `Policy`、`Evidence`、`Persistence` 通过明确接口接入，不允许任意模块直接调用其实现细节。

## 2. Interface Layer

包括桌面端 API、REST、WebSocket、CLI 和 MCP。

允许：

- 认证、传输协议映射和 DTO 转换
- 调用 Application Use Case
- 将领域事件转换为客户端事件

禁止：

- 直接执行设备动作
- 直接写数据库
- 包含 Skill 或策略业务逻辑
- 根据客户端类型绕过权限

独立 MCP stdio 进程只能通过固定 loopback Runtime API 调用 Application，不得另建共享数据目录的
Runtime 实例，也不得读取 SQLite、Artifact 文件或平台 Adapter。

## 3. Application Layer

包括 Task Engine、Skill Runtime、Tool Registry 和应用用例。

职责：

- 编排领域对象和端口
- 控制事务、状态转换和取消
- 解析 Capability
- 通过 Policy Engine 授权

禁止依赖具体客户端和具体平台 Adapter。

## 4. Domain Layer

包含核心模型、错误、状态机和策略规则。

- 必须可在无数据库、网络、设备和框架环境中测试。
- 不导入 FastAPI、SQLAlchemy、Tauri、ADB 或模型 SDK。
- 不读取环境变量和全局配置。

## 5. Device Gateway

提供平台无关的设备端口、Device Registry、Session 和设备锁。

- 使用 capability 表达差异。
- 不假设所有平台存在 serial、package name 或 Activity。
- 将 Adapter 错误映射为统一领域错误。
- 负责同一设备写动作串行化。

## 6. Platform Adapter

Adapter 只实现平台能力映射。

- Android Adapter 是唯一允许调用 ADB Runner 的区域。
- Adapter 不调用模型。
- Adapter 不判断用户目标是否完成。
- Adapter 不自行降低风险等级。
- 平台不支持能力时明确返回 `CAPABILITY_UNAVAILABLE`。

## 7. Tool 与 Skill

Tool 是原子、确定性、受策略约束的动作。Skill 是目标级能力，可组合 Tools 并执行验证。

- Skill 只能调用注册 Tool 或其他明确允许的 Skill。
- Agentic Skill 必须设置 Tool allowlist、最大步数、超时和连续失败阈值。
- Tool 不接收自由格式 Shell。
- Skill 完成必须有可验证证据，不能仅依赖模型自述。
- Agent 决策动作分为 `run_tool`、`run_skill` 和 `finish`。`run_tool` 是页面探索和动态交互的默认路径；`run_skill` 只用于边界稳定、可复用、可验证的目标级能力；`finish` 必须由 Runtime 确定性验证。
- 不得将滚动方向选择、页面路径探索、点击目标选择和失败恢复等动态 Agent 决策隐藏进普通 Skill 黑盒。

## 8. 依赖检查

建立代码后应通过自动化规则检查：

- Domain 的禁用 import
- Desktop 不得出现 ADB 调用
- Interface 不得导入 Adapter 实现
- Generated contracts 不得手工修改

新增例外必须通过 ADR，而不是添加忽略规则掩盖。
