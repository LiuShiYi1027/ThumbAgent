# Mobile Agent V1 技术方案

> 状态：Active
> 版本：V1.0
> 更新日期：2026-07-03
> 关联文档：[产品定位](../product/positioning.md) · [第一版产品方案](../product/solution-v1.md)

## 1. 技术目标

V1 建立一个本地运行、可扩展到多平台的 AI-to-Device Runtime，使桌面端和外部 AI Agent 能够通过同一组 Skills 安全操作一台 Android 设备。

技术方案需要优先满足：

- **可靠**：动作执行后必须重新观察并验证，不能只判断命令是否退出成功。
- **可控**：模型不能直接执行 Shell，只能调用注册的 Tool 和 Skill。
- **可观察**：任务、动作、Observation、证据和错误均可追踪。
- **可扩展**：Android、iOS、鸿蒙通过 Adapter 接入，上层协议不暴露平台命令细节。
- **本地优先**：设备通信、执行记录和敏感数据默认保留在本机。
- **可嵌入**：桌面端、CLI、MCP 和本地 API 共享同一套 Runtime。

## 2. V1 技术范围

### 2.1 本期实现

- macOS 桌面工作台
- 单台 Android 真机或模拟器
- USB 与已建立的 ADB 网络连接
- 设备发现和基础信息读取
- 截图、前台应用和 UI 树采集
- 打开应用、点击、输入、滑动、Back、Home 和等待
- Tool Registry 与 Skill Registry
- 简单 Agent Observe–Act–Verify 循环
- 风险策略、暂停、取消和人工接管
- SQLite 任务数据与文件证据存储
- localhost REST API 与 WebSocket 事件流
- MCP stdio 开发者预览接口

### 2.2 本期不实现

- iOS 与鸿蒙真实设备 Adapter
- 多设备并发调度
- 任意 Shell 执行
- 高帧率视频流与低延迟远程控制
- APK 安装、卸载和清除数据
- Logcat 长时采集与性能分析
- 云端账号、团队空间和同步
- Agent 自动处理支付、密码或验证码

## 3. 总体架构

```text
┌──────────────────────────────────────────────────────────────┐
│ Clients                                                      │
│ Desktop Workbench │ CLI │ MCP Client │ Local API Consumer    │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Interface Layer                                               │
│ REST API │ WebSocket Events │ MCP stdio                      │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Mobile Agent Runtime                                          │
│ Task Engine │ Agent Loop │ Skill Registry │ Tool Registry     │
│ Policy Engine │ Capability Resolver │ Evidence Service        │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Device Gateway                                                │
│ Device Registry │ Session Manager │ Adapter Interface         │
└──────────────┬────────────────┬────────────────┬──────────────┘
               │                │                │
       Android Adapter     iOS Adapter      Harmony Adapter
           V1 实现            预留              预留
               │
       ADB / UIAutomator / Device Services
```

## 4. 架构决策

### 4.1 Runtime 与桌面端分进程

桌面端负责交互和展示，Runtime 负责设备、任务、Skills、安全和数据。

选择分进程的原因：

- Runtime 可独立被 CLI 和 MCP 使用。
- UI 崩溃或刷新不应直接终止设备任务。
- 后续可将 Runtime 部署到设备实验室节点。
- Python 生态适合设备工具、AI SDK 和数据分析，桌面 UI 可独立采用 Web 技术。

V1 桌面应用启动 Runtime sidecar，Runtime 只监听 `127.0.0.1` 随机端口，并使用一次性会话令牌认证。

### 4.2 V1 使用 ADB 原生命令，不强依赖 Appium

V1 的动作集合较小，直接封装 ADB 能减少服务、Node.js 和 Driver 管理成本。

Android 结构化感知采用 UIAutomator 导出的 UI hierarchy；截图、包名、输入和系统按键使用 ADB 能力。后续需要更强元素等待、WebView 或复杂测试生态时，再增加 Appium/UiAutomator2 Provider，不改变上层 Tool Schema。

Android 官方 UI Automator 能够跨应用和系统界面查找并操作元素，适合作为后续设备端 helper 的基础：[Android UI Automator](https://developer.android.com/training/testing/other-components/ui-automator)。Appium 的 UiAutomator2 Driver 可作为后续可选 Provider：[Appium UiAutomator2](https://appium.io/docs/en/2.11/quickstart/uiauto2-driver/)。

### 4.3 MCP 作为外部 Agent 接口，不作为内部总线

Runtime 内部使用类型明确的 Python 接口和领域事件，避免把内部模块耦合到 MCP 协议。

MCP Server 只是 Interface Adapter。V1 优先支持适合本地集成的 `stdio`，后续按需增加 Streamable HTTP。MCP 官方定义的标准传输包括 stdio 和 Streamable HTTP：[MCP Transports](https://modelcontextprotocol.io/specification/draft/basic/transports)。

### 4.4 Skills 声明与执行代码分离

Skill Manifest 描述名称、输入输出、风险和能力要求；Skill Handler 实现执行逻辑。Manifest 可被桌面端、MCP 和模型共同读取，但只有受信任代码能够注册 Handler。

V1 不允许从任意目录动态加载未经签名的第三方执行代码。

## 5. 建议技术栈

### 5.1 Desktop Workbench

- Tauri 2
- React + TypeScript
- Vite
- TanStack Query：服务端状态
- Zustand：轻量本地 UI 状态
- WebSocket：任务事件与设备状态

Tauri 负责窗口、应用生命周期、Runtime sidecar 启停和本地能力授权。前端不得直接启动 ADB 或执行系统命令。

### 5.2 Local Runtime

- Python 3.11+
- FastAPI：localhost API
- Pydantic：协议和配置校验
- SQLAlchemy 2 + Alembic：持久化与迁移
- SQLite：V1 元数据存储
- asyncio：任务和子进程调度
- structlog：结构化日志
- Pillow：截图元数据和缩略图处理

### 5.3 Agent 与模型层

- 自研有限状态 Agent Loop
- Provider 抽象支持 OpenAI-compatible、多模态本地服务和无模型规则模式
- JSON Schema / Structured Output 约束模型动作
- 不引入重型通用 Agent Framework 作为核心依赖

V1 的重点是执行可靠性与边界，不是构建任意自主 Agent。

ITER-0013 起，Runtime 提供 `agent.run` 预览任务入口。该入口先使用 deterministic Planner 验证 Observe–Plan–Act–Report 骨架：Planner 输出结构化决策，Runner 再做 allowlist 校验并调用既有 Skill。真实 LLM 接入时只替换 Planner Provider，不能绕过 Tool Registry、Policy Engine、Device Gateway 或 Task Store。

ITER-0015 起，Runtime 增加 LLM Planner 内部预览契约。模型式输出先解析为 `AgentDecision`，字段、类型、`confidence` 范围和必要 selector 均需校验；即使结构合法，Runner 仍必须执行 Skill allowlist 校验。该阶段只提供 `MockLLMPlanner`，不调用真实模型服务。

ITER-0016 起，Runtime 增加默认关闭的 OpenAI-compatible Planner Provider 预览。Provider 负责构造最小 chat-completions 请求、注入 transport、解析结构化 JSON 响应并复用 Planner 契约校验。默认 Runtime 仍使用 deterministic Planner；真实 Provider 启用必须经过后续显式配置和授权。

ITER-0017 起，Runtime 提供模型 Provider 配置门。`ModelProviderSettings(enabled=false)` 必须返回无模型的 `RuleBasedPlanner`；启用 OpenAI-compatible Provider 时，配置只保存 `api_key_ref`，真实密钥由注入的 `SecretResolver` 提供。默认 Runtime 不读取环境变量、配置文件或 Keychain，也不自动启用云模型。

ITER-0018 起，Runtime 和本地 Web UI 提供模型 Provider 只读状态面板。状态 API 只返回 provider/model、启用状态和密钥引用是否存在，不返回真实密钥或 `api_key_ref` 原文。该面板用于产品可见性，不承担配置编辑或模型启用职责。

ITER-0019 起，Runtime 可从 `<data-dir>/model-provider.json` 或 `MOBILE_AGENT_MODEL_CONFIG` 指定文件读取模型 Provider 配置，并允许 `MOBILE_AGENT_MODEL_*` 环境变量覆盖字段。配置文件只保存密钥引用；开发预览的 `EnvironmentSecretResolver` 仅解析 `env:MOBILE_AGENT_MODEL_SECRET_*`，避免形成任意环境变量读取通道。默认 Agent Runner 仍不因配置存在而自动调用真实模型。

ITER-0020 起，默认 Runtime 会将模型配置映射为 Agent Runner 使用的 Planner：关闭时使用 `RuleBasedPlanner`；配置可用时使用 OpenAI-compatible Planner；配置启用但不可用时使用 `UnavailablePlanner` 返回 `MODEL_UNAVAILABLE`。该设计避免静默回退造成误导，同时保持模型输出必须经过 AgentDecision 解析、Skill allowlist、Policy Engine 和 Device Gateway。

ITER-0021 起，本地 Web UI 将模型 Provider 运行态展示为用户可理解的状态卡片。`active` 状态提示模型输出仍受 allowlist 和 Policy 约束；`unavailable` 状态展示脱敏错误摘要，并提示检查本地配置和 `MOBILE_AGENT_MODEL_SECRET_*`。配置示例位于 `docs/examples/model-provider.example.json`。

ITER-0022 起，Agent Preview 支持多轮 Tool 决策。Planner 可以输出 `run_tool` 与 `finish`；Runtime 在每轮执行前校验 Tool allowlist、Capability 和 Policy，执行后重新 Observation。`finish` 不能只依赖模型自述，必须携带 `expected_selector` 并由 Runtime 在当前 UI hierarchy 中确定性验证。旧的 `run_skill` 决策保留为兼容路径。

ITER-0023 起，Agent 每轮报告中的 `AgentObservationSummary`、`AgentDecision` 和 `AgentStepResult` 纳入公共 JSON Schema。`TaskRun` Schema 正式支持 `agent.run`、`agent_round` 和 `agent.round`，每轮结果固定包含 `action_result`、`skill_result`、`verified_node` 三类可空输出槽位，便于桌面端、CLI 和未来 MCP 外部接口稳定渲染 Observe–Plan–Act 时间线。

ITER-0024 起，Agent Runner 在 Tool 执行后比较前后 foreground app 与 UI tree，生成 `AgentActionFeedback`。该反馈进入下一轮 Observation，帮助 Planner 在页面无变化时调整方向或动作；若 Planner 仍重复完全相同的无进展 ToolCall，Runtime 在再次派发前以 `NO_PROGRESS` 停止。Runtime 不替模型改写动作参数，保持 Planner 决策与执行安全边界清晰。

ITER-0025 起，Agent Observation 不再按 UI hierarchy 原始顺序截取前 30 个节点，而是先过滤结构噪声、脱敏常见标识符、按语义与可操作性排序并去重，再生成有界摘要。摘要公开候选总数、截断状态和可点击祖先信息；完整 UI Tree 继续只作为本地证据与确定性定位输入，不直接发送给模型 Provider。

ITER-0026 起，`run_tool` 使用独立的 `AgentToolCall` JSON Schema 和 Runtime 参数校验。`input.tap_element` 必须显式携带 `resolve_clickable_ancestor=true`，避免模型看到文本节点却点击到不可点击的子节点。OpenAI-compatible Provider 遇到 `MODEL_OUTPUT_INVALID` 时最多追加一次脱敏、结构化的修复请求；修复期间不派发设备动作。只有通过 Contract 与 allowlist 校验的决策才进入执行；此后的 Tool 失败会在失败 step 中保留当轮 Observation 和 Decision，便于定位语义、参数或设备问题。

ITER-0027 起，Agent 评测不以历史 ToolCall 序列作为正确答案。`AgentEvaluationScenario` 只定义用户目标、独立成功判定、禁用 Tool 和轮次预算；真实设备 E2E 仍使用当前模型对最新 Observation 逐轮规划。`AgentEvaluator` 只消费已持久化的 `TaskRun`，不调用 Adapter、不重放设备动作，并输出目标是否达成、轮次、Tool 数、页面进展、模型修复、策略违规和耗时等指标。历史轨迹只用于 Runtime/Contract/Policy 的确定性回归，不用来声称模型对改版 App 的泛化能力。

ITER-0042 起，多个 `AgentEvaluationScenario` 可以组成版本化 Suite。Suite 只声明运行次数、目标、
成功条件与约束；设备任务仍由现有 Web/MCP 异步入口逐个执行。只读聚合器消费单任务评测结果，要求
完整场景覆盖并输出成功率、耗时分位数和可靠性指标，不访问 Adapter、Planner 或 Task Store，也不
将历史 ToolCall 固化为回放工作流。

ITER-0043 起，`app.list` 与 `app.inspect` 两个确定性 Skill 通过 `app.inspect@1` Capability 读取
设备包管理器的最小必要元数据。Client/MCP 只调用 Runtime REST，Runtime 在 Session 与 Lease 边界内
调用 Tool，Tool 再经过 Capability Catalog 与 Policy Engine 到达 Device Gateway。Android Adapter
只构造固定的 `pm list packages` 和 `dumpsys package <validated-app-id>` 参数数组，并在公共响应前
丢弃 APK 路径、签名、权限与原始输出。安装仍是独立 High 风险能力，不复用该只读 Capability。

ITER-0044 的 `app.install` 使用两阶段 High 风险协议。Prepare 在 Runtime 授权的 `<data-dir>/apks`
目录内读取单 APK，计算 SHA-256 并从 bounded binary Manifest 提取 package id，然后生成十分钟有效、
单次使用的内存 Approval。Submit 只携带 approval id；Runtime claim 后才向 Policy Engine 提供内部
High-risk 授权位。异步任务持有 Lease/Session，Android Adapter 只执行固定 `adb install` 或
`adb install -r`，随后通过 package manager 查询验证。详见 [ADR-0016](../adr/0016-scoped-high-risk-approval.md)。

ITER-0045 的 `app.uninstall` 使用独立两阶段 High 风险协议。Prepare 读取最小应用元数据并要求
`system_app=false`，影响摘要明确展示是否删除应用数据；Approval 绑定设备、包名、版本和
`keep_data`。Submit 后 Android Adapter 只执行固定 `adb uninstall [ -k ] <app-id>`，再读取应用
清单确认目标包不存在。超时或断连视为 unknown outcome，不自动重试。详见
[ADR-0017](../adr/0017-scoped-app-removal.md)。

ITER-0046 将应用生命周期收敛为统一的确定性任务链路。只读状态通过固定的 package、process 和
window 查询归一化为 `AppRuntimeState`；启动复用 `app.open` 并验证目标包进入前台；停止只允许
已确认的非系统应用并验证进程消失、目标退出前台。清除数据采用独立 Prepare/Submit：Approval
绑定设备、包名和版本，Submit 后 Adapter 只执行固定 `pm clear --user 0 <app-id>`，再验证应用仍
安装且运行状态复位。REST 和 MCP 只接受类型化参数，不暴露 PID、原始系统输出或任意命令参数。

ITER-0047 将已有诊断能力组合为 `device.diagnostics.bundle`。Tool 在执行任何敏感读取前完成
Capability 与 Medium 风险确认校验，然后在同一 Task Session 和 Lease 中采集 Observation、脱敏
日志、聚合性能及可选应用状态。Bundle Builder 只读取本次生成的受信任 Artifact，逐项复核大小与
SHA-256，并写入固定文件集合和版本化 Manifest；路径由 ArtifactStore 分配，总大小限制为 24 MiB。
REST、MCP、CLI 和 Web 仅展示摘要及 Artifact 元数据，不内联包内容、不上传数据，也不开放通用
文件读取接口。部分采集失败时，Task 报告保留已完成证据引用以便定位问题。

ITER-0048 为本地证据增加显式保留和删除边界。`GET /v1/storage` 只返回 Artifact 数量、分类和
字节聚合；Cleanup Prepare 以保留周期和单次上限确定候选，并在内存 Approval 中绑定每个系统生成
文件的 Artifact ID、相对路径、大小与 SHA-256。Submit 是 High 风险异步本地任务，不绑定设备
Session 或 Lease；每个文件删除前重新验证范围和完整性，并在文件之间响应取消与 Deadline。任务、
事件、配置、密钥、APK、未知文件和任意用户路径均不属于清理范围。

ITER-0051 起，`AgentRunner` 对观察阶段的瞬时 `DEVICE` 类错误（`UI_TREE_INVALID`、
`OBSERVATION_FAILED`）做最多 2 次有界重试，重试间检查取消与 Deadline；连接性错误仍立即
终止。`max_rounds` 允许范围放宽到 1–12，默认值 6 不变。

ITER-0052 起，Runtime 提供证据内容的唯一读取通道
`GET /v1/artifacts/{artifact_id}/content`：仅截图 PNG、Bearer token 认证、单文件 8 MiB
上限、no-store，不开放其他 Artifact 类型或任意路径。`task.step_completed` 事件 payload
携带该轮动作后截图的 `screenshot_artifact_id`，桌面工作台据此在执行中与报告内展示设备画面；
桌面 IPC 增加仅匹配该端点模式的二进制白名单桥，截图只在 webview 内存中渲染。

ITER-0028 起，Agent Runner 将未产生设备副作用的目标定位失败和 `finish` 验证失败记为可恢复 failed round，并将错误码和有界候选详情交给下一轮 Planner。`finish` 可同时验证前台 app/activity 与唯一 UI Selector；相同无进展决策仍会被阻止。语义点击在派发前排除屏幕顶部系统区和底部手势区的启发式安全边距。Provider 边界保留 timeout、HTTP status、connection 和 invalid JSON 的脱敏分类，且只对 retryable 模型请求最多重试一次；Selector 校验只保留字段名、未知键等结构诊断，不记录字段值。详见 [ADR-0006](../adr/0006-recoverable-agent-verification.md)。

ITER-0029 起，调用方可以通过 `AgentGoalAcceptance` 为 `agent.run` 提供独立成功条件。模型仍
负责基于实时页面动态规划，并决定何时请求 `finish`；一旦存在外部成功条件，Runtime 使用
app id、Activity 和唯一 Selector 的 all-of 结果作为权威终态，不采信模型临时生成的完成
Selector。验证失败发生在只读阶段，可反馈模型继续规划；未提供成功条件时保持原有兼容行为。
TaskRun 持久化 `goal_acceptance` 和 `completion_source`，使客户端能够区分模型条件、Runtime
条件和 Skill 结果。详见 [ADR-0007](../adr/0007-runtime-owned-goal-verification.md)。

ITER-0030 起，自然语言目标可以先经过无设备副作用的 `GoalCompiler` 生成 `AgentGoalSpec`
草案。模型只提供增强执行目标、显式假设、置信度和可选成功条件；Runtime 注入编译来源并强制
`source=llm` 的草案要求确认。确认后 Agent Runner 以 `execution_goal` 规划，但 TaskRun 保存
原始 `source_goal` 和完整 GoalSpec。该阶段不生成 ToolCall 序列，不把编译器变成固定路径规划器。
详见 [ADR-0008](../adr/0008-confirmed-goal-compilation.md)。

ITER-0031 起，长耗时 Agent 任务可以通过独立异步资源提交。`TaskExecution` 保存排队、运行、
取消中和终态快照，增量 TaskEvent 在每轮结束时持久化；终态 TaskRun 仍是完整报告真源。
V1 由单工作线程串行执行异步任务，取消只在安全边界阻止后续动作。Runtime 重启会终止非终态
执行并记录 `TASK_INTERRUPTED`，不会重放 ToolCall。原同步 API 保留兼容，Web 默认使用异步
入口并通过 REST 重建状态。详见 [ADR-0009](../adr/0009-durable-async-task-execution.md)。

ITER-0032 起，Runtime Application 层为公开设备写入口持有独占 `DeviceLease`。Agent 在完整任务
期间持有租约，内部 Tool 不重复加锁；直接 Tool/Skill 使用短租约。租约期限只用于诊断，不能在
未知设备动作仍可能运行时自动抢占。Agent 同时持有总 `deadline_seconds`，Runner 在安全边界
检查预算并以 timed_out 终止后续动作。详见 [ADR-0010](../adr/0010-device-lease-task-deadline.md)。

ITER-0033 起，同一 Runtime 数据目录通过非阻塞文件锁限制为单实例，避免不同端口的两个进程
共享 SQLite、令牌和设备。Device Gateway 用 `session_id` 标识一段连续在线连接；Task 在取得
DeviceLease 时绑定当前 Session，并在每次 Observation 与动作前复核。设备消失、离线后重连会
生成新 Session，旧任务以 `DEVICE_SESSION_CHANGED` 停止且不会自动续跑。详见
[ADR-0011](../adr/0011-runtime-instance-device-session.md)。

ITER-0034 起，Runtime 提供只读 `RuntimeReadiness` 快照，由 Application 层组合 Device Gateway、
Device Session 和 DeviceLease 状态。ADB 缺失时默认 Runtime 使用拒绝所有设备访问的
UnavailableDeviceAdapter 保持 Web/CLI 诊断接口可启动；客户端不得据此绕过 Gateway。Readiness
不执行 Observation、模型调用或设备动作，blocked 也是 HTTP 200 的可渲染产品状态。

ITER-0035 起，Capability Catalog 成为能力风险、幂等性、验证要求和限制的元数据真源，Tool
Registry 从中派生执行定义。DeviceInspection 只组合设备发现、Session、Lease、Catalog 与 Tool
映射，不触发 Observation 或动作；展示的 confirmation_required 不能替代 Policy Engine 授权。

ITER-0036 起，`device.logs.collect` 作为首个工程诊断 Skill 接入。底层
`device.logs.capture` 虽登记在 Tool Registry，但标记为不可从通用 UI Action 入口直接调用；Skill
完成 Capability、Policy、Session 和 Lease 校验后由 Device Gateway 调用平台 Adapter。Android
只构造固定、有界 logcat 快照参数，输出脱敏后保存为 `device_log` Artifact，公共结果不内联正文。

ITER-0037 起，AsyncTaskExecutor 支持代码内显式登记的 `agent.run` 与 `device.logs.collect`，但不
接受客户端动态 task_type 或 handler。日志任务复用 TaskExecution、TaskEvent、TaskRun、Deadline、
Session、Lease、幂等与 Runtime 重启恢复；同步 Skill 保持兼容，Web 默认提交异步诊断任务。详见
[ADR-0013](../adr/0013-explicit-multi-type-async-execution.md)。

ITER-0038 起，`device.performance.snapshot` 通过固定 Android diagnostics 生成平台无关聚合指标。
Adapter 内解析并丢弃包含进程明细的原始输出；上层只接收 percent、bytes、seconds 和 Celsius
字段，并保存规范化 JSON Artifact。日志与性能任务共享内部 DiagnosticTaskRunner，但 Task 类型和
Skill Handler 仍由 Runtime 显式注册。详见 [ADR-0014](../adr/0014-aggregate-performance-snapshot.md)。

ITER-0039 起，Runtime Application 层提供只读性能比较 Use Case。调用方提交两个已经完成的
`device.performance.snapshot` task_id；Runtime 通过 TaskStore 验证任务类型、成功状态、同设备和
采集顺序，再由 Domain 计算带单位和公开稳定阈值的两点 delta。比较不调用 Adapter、模型或原始
Artifact，也不将动态业务任务固化为回放 Workflow；结果只描述方向，不自动判定回退或因果。

ITER-0040 起，MCP stdio 作为独立 Interface Adapter 调用已启动 Runtime 的固定 localhost REST
端点，不直接构造 Runtime、访问 SQLite、读取 Artifact 或执行 ADB。MCP 只公开目标级 Tools；耗时
设备操作提交为现有异步 TaskExecution 并返回 task_id。协议支持严格初始化、Schema 校验、调用限流
和 structured error，同时保持 Policy、Capability、Session 与 Lease 为 Runtime 权威边界。详见
[ADR-0015](../adr/0015-mcp-stdio-local-api-adapter.md)。

模型输出中的 `reason` 是审计元数据，不参与 Tool 授权和完成验证。模型省略或返回空白
`reason` 时，解析器生成固定非空审计说明，保持公共 `AgentDecision` Contract 不变且不增加一次
付费修复请求；非字符串或超长 `reason` 仍视为无效输出。决策类型、参数、Selector、allowlist
和 Policy 不因该兜底而放宽。

长期 Agent 决策动作模型采用三类语义：

- `run_tool`：Agent Loop 的默认动作形态，用于页面探索、点击、滑动、返回、等待等需要逐轮观察和动态调整的原子动作。
- `run_skill`：保留为目标级受控能力入口，用于安装包、采集日志、导出诊断包、性能采样等边界稳定、输入输出明确、验证器稳定的复合能力。
- `finish`：模型请求结束任务，但成功与否必须由 Runtime 根据结构化验证条件确定，不能只依赖模型自述。

页面路径探索、滚动方向选择、点击目标选择和失败恢复优先通过 `run_tool` 多轮完成；不得为了简化 prompt 将这类动态决策隐藏进 Skill。详见 [ADR-0005](../adr/0005-agent-decision-action-model.md)。

### 5.4 Android Adapter

- Android Platform Tools / ADB
- UIAutomator hierarchy
- `adb exec-out screencap -p` 截图
- Android system services / package manager 的只读查询
- 输入事件和 Activity 启动能力

所有命令必须通过参数数组调用子进程，不拼接 Shell 字符串。

## 6. 代码仓库结构

建议采用 Monorepo：

```text
mobile-agent/
├── apps/
│   └── desktop/                 # Tauri + React
├── runtime/
│   ├── mobile_agent/
│   │   ├── api/                 # REST / WebSocket
│   │   ├── agent/               # Planner 与 Agent Loop
│   │   ├── domain/              # 领域模型与状态机
│   │   ├── skills/              # Skill manifests 与 handlers
│   │   ├── tools/               # Tool schemas 与 handlers
│   │   ├── devices/             # Gateway、Registry、Session
│   │   │   └── adapters/
│   │   │       ├── base.py
│   │   │       └── android/
│   │   ├── policy/              # 风险与授权
│   │   ├── evidence/            # 截图与报告
│   │   ├── persistence/         # SQLite repositories
│   │   └── providers/           # Model providers
│   ├── tests/
│   └── pyproject.toml
├── interfaces/
│   ├── mcp/                     # MCP server adapter
│   └── cli/                     # CLI adapter
├── contracts/
│   ├── schemas/                 # JSON Schema
│   └── generated/               # TS/Python 生成类型
└── docs/
    ├── product/
    ├── architecture/
    ├── engineering/
    ├── iterations/
    └── adr/
```

## 7. 核心领域模型

### 7.1 Device

```json
{
  "device_id": "adb:emulator-5554",
  "platform": "android",
  "name": "Pixel_8_API_35",
  "model": "sdk_gphone64_arm64",
  "os_version": "15",
  "connection": "online",
  "capabilities": [
    "screen.observe",
    "app.launch",
    "input.tap",
    "input.text",
    "input.swipe",
    "navigation.back",
    "navigation.home"
  ]
}
```

`device_id` 是 Runtime 内的稳定复合标识，不直接假设所有平台都使用 serial。
`session_id` 不是设备永久身份，而是一段连续在线连接的短期身份；执行与审计使用
`(device_id, session_id)` 防止断连前任务跨到重连后的设备状态。

### 7.2 Observation

```json
{
  "observation_id": "obs_01...",
  "device_id": "adb:emulator-5554",
  "captured_at": "2026-07-03T14:00:00Z",
  "foreground_app": {
    "app_id": "com.android.settings",
    "activity": ".Settings"
  },
  "screen": {
    "width": 1080,
    "height": 2400,
    "orientation": "portrait",
    "screenshot_ref": "artifact://..."
  },
  "ui_tree_ref": "artifact://...",
  "ui_summary": [],
  "device_state": "interactive"
}
```

Observation 是不可变快照。动作前后必须分别保存，避免后续截图覆盖现场。

### 7.3 ToolCall

```json
{
  "tool_call_id": "call_01...",
  "task_id": "task_01...",
  "device_id": "adb:emulator-5554",
  "tool": "input.tap",
  "arguments": {
    "target": {
      "strategy": "text",
      "value": "网络和互联网"
    }
  },
  "risk": "low",
  "status": "requested"
}
```

### 7.4 Task

```json
{
  "task_id": "task_01...",
  "goal": "打开系统设置",
  "device_id": "adb:emulator-5554",
  "constraints": ["不得修改任何系统设置"],
  "status": "running",
  "max_steps": 12,
  "deadline_seconds": 120
}
```

## 8. Tool 设计

### 8.1 Tool 命名

使用稳定的领域命名，不使用底层命令名：

```text
device.list
device.inspect
screen.observe
app.launch
input.tap
input.text
input.swipe
navigation.back
navigation.home
task.wait
```

### 8.2 目标定位协议

```json
{
  "strategy": "resource_id | text | content_description | bounds | coordinates",
  "value": "string | object",
  "match": "exact | contains",
  "index": 0
}
```

定位优先级：

1. resource ID
2. content description
3. 精确文本
4. 文本包含与结构关系
5. bounds 中心点
6. 绝对坐标

模型返回语义目标，Tool Handler 使用最新 Observation 解析为坐标。ToolCall 中同时保存原始 selector、命中节点和最终坐标。

### 8.3 Tool 执行管线

```text
Schema Validation
→ Device Binding
→ Capability Check
→ Policy Evaluation
→ Optional Confirmation
→ Adapter Execution
→ Post-action Delay / Stability Check
→ New Observation
→ Result Verification
→ Audit Event
```

## 9. Skill 设计

### 9.1 Skill Manifest

```yaml
id: app.open
version: 1.0.0
name: Open application
description: Open an application on a selected mobile device and verify it is foreground.

input_schema:
  type: object
  required: [device_id, app]
  properties:
    device_id:
      type: string
    app:
      type: string

output_schema:
  type: object
  required: [success, observation_id]

required_capabilities:
  - app.launch
  - screen.observe

risk: low
timeout_seconds: 30
```

### 9.2 V1 Skill Handler 类型

- Deterministic Skill：固定步骤与验证，例如 `discover_devices`、`open_app`。
- Agentic Skill：允许模型在受限 Tool 集内迭代，例如 `execute_mobile_task`。

Agentic Skill 必须声明：

- 可调用 Tool allowlist
- 最大步骤数
- 总超时
- 每步风险上限
- 成功判定方式
- 连续失败阈值

## 10. Agent Loop

V1 使用有限状态循环：

```text
Prepare
→ Observe
→ Decide
→ Validate Action
→ Execute
→ Observe Again
→ Verify Progress
→ Complete / Continue / Ask User / Fail
```

### 10.1 每轮输入

模型仅接收：

- 用户目标和约束
- 当前任务摘要
- 最新 Observation 的屏幕截图与压缩 UI 摘要
- 最近若干动作及结果
- 当前允许调用的 Tools
- 剩余步骤和时间预算

不把完整历史 UI XML 在每轮重复发送给模型。

### 10.2 每轮输出

```json
{
  "assessment": "当前位于设置首页，需要打开网络页面",
  "action": {
    "tool": "input.tap",
    "arguments": {
      "target": {
        "strategy": "text",
        "value": "网络和互联网",
        "match": "exact"
      }
    }
  },
  "expected_change": "页面标题变为网络和互联网",
  "completion": false
}
```

模型的 `assessment` 只用于解释和调试，不视为可信事实；动作和完成状态必须由 Runtime 校验。

### 10.3 防循环机制

- 默认最多 12 步
- 同一动作与相似 Observation 连续出现 2 次时触发重新规划
- 连续 3 次无进展则请求人工介入
- 单步超时默认 15 秒，任务总超时默认 120 秒
- 设备断连立即暂停，不继续生成动作

## 11. Android Adapter

### 11.1 Adapter 接口

```python
class DeviceAdapter(Protocol):
    async def list_devices(self) -> list[Device]: ...
    async def inspect(self, device_id: str) -> Device: ...
    async def observe(self, device_id: str) -> Observation: ...
    async def launch_app(self, device_id: str, app_id: str) -> ActionResult: ...
    async def tap(self, device_id: str, x: int, y: int) -> ActionResult: ...
    async def input_text(self, device_id: str, text: str) -> ActionResult: ...
    async def swipe(self, device_id: str, gesture: Swipe) -> ActionResult: ...
    async def key_event(self, device_id: str, key: Key) -> ActionResult: ...
    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes: ...
```

### 11.2 ADB Runner

ADB Runner 是唯一允许启动 `adb` 子进程的模块，负责：

- 二进制路径解析和版本检查
- 参数数组构造
- 每条命令绑定设备 serial
- 超时、取消和输出大小限制
- stdout/stderr 脱敏
- 并发锁和设备级串行化
- 结构化错误映射

禁止使用 `shell=True`。禁止将模型文本直接作为 adb shell 参数执行。

### 11.3 Observation 采集

一次标准 Observation：

1. 检查设备仍在线且处于可交互状态。
2. 获取屏幕尺寸与方向。
3. 获取前台应用与 Activity。
4. 获取 PNG 截图。
5. 导出 UI hierarchy。
6. 解析、裁剪和标准化可见节点。
7. 将原始文件写入 Artifact Store。
8. 返回结构化摘要和引用。

截图与 UI 树可能存在几十到几百毫秒的时间差，Observation 中需要分别保存采集时间。后续如需原子性更强的感知，再引入设备端 helper。

### 11.4 文本输入限制

ADB 文本输入对空格、特殊字符和非拉丁字符支持不一致。V1：

- 普通 ASCII 走 ADB 输入。
- 非 ASCII 或复杂文本检测后标记能力不足，提示人工输入。
- 不静默修改用户文本。
- 后续通过受控输入法 helper 增强。

## 12. API 设计

### 12.1 REST API

```text
GET    /v1/health
GET    /v1/devices
GET    /v1/devices/{device_id}
POST   /v1/devices/{device_id}/observe
GET    /v1/skills
POST   /v1/skills/{skill_id}/invoke
POST   /v1/tasks
GET    /v1/tasks/{task_id}
POST   /v1/tasks/{task_id}/pause
POST   /v1/tasks/{task_id}/resume
POST   /v1/tasks/{task_id}/cancel
POST   /v1/tasks/{task_id}/confirmations/{confirmation_id}
GET    /v1/tasks/{task_id}/artifacts
```

所有变更操作支持 `Idempotency-Key`。任务创建返回 `202 Accepted` 与 `task_id`，不保持长 HTTP 请求等待任务完成。

ITER-0006 期间先提供一个预览型同步任务运行端点：

```text
POST   /v1/tasks/settings.scroll_navigate/run
GET    /v1/tasks/{task_id}
GET    /v1/tasks/{task_id}/events
GET    /v1/tasks?limit=N
GET    /ui
```

这些端点只包装已有 `settings.scroll_navigate` Skill，并保存 `TaskRun` 与紧凑 `TaskEvent`；它们不替代后续正式异步 `/v1/tasks` 队列、实时事件流和运行中任务恢复语义。

ITER-0011 提供 `/ui` 本地 Web 页面，作为桌面端任务历史和报告详情的无构建原型。该页面只调用 GET API，不触发设备动作。

ITER-0012 在 `/ui` 中加入固定安全 demo 任务按钮。浏览器 POST 仍需要 Runtime token，且只允许同源 loopback Origin；任意外部 Web Origin 不能触发设备动作。

### 12.2 WebSocket 事件

```text
device.connected
device.disconnected
observation.created
task.status_changed
task.step_started
task.step_completed
task.awaiting_confirmation
artifact.created
task.completed
```

事件包含 `event_id`、`occurred_at`、`task_id`、`device_id` 和递增的 task sequence，前端可检测丢失事件后通过 REST 重建状态。

### 12.3 MCP 映射

MCP V1 暴露目标级 Skills，不默认暴露所有原子 Tools：

```text
mobile_list_devices
mobile_inspect_device
mobile_observe_screen
mobile_open_app
mobile_execute_task
mobile_get_task
mobile_cancel_task
```

MCP 调用仍然经过相同 Policy Engine，不能绕过桌面端的风险策略。

## 13. 任务状态机与并发

### 13.1 状态机

```text
draft → ready → running
                  ├→ paused → running
                  ├→ awaiting_confirmation → running / cancelled
                  ├→ awaiting_user → running / cancelled
                  ├→ unknown_outcome → awaiting_user / failed / succeeded
                  ├→ succeeded
                  ├→ failed
                  ├→ timed_out
                  └→ cancelled
```

状态转换由 Task Engine 统一提交，UI 和 Skill Handler 不能直接修改数据库状态。

### 13.2 并发策略

V1 支持系统识别多台设备，但同一时刻只允许一个 active task。设计上仍采用每设备互斥锁：

- 一个设备同一时间只能有一个写动作任务。
- 只读观察可以按策略与任务共享，但必须限流。
- 人工接管会暂停该设备上的 Agent 动作。
- Runtime 重启后，未开始的任务可恢复为 `ready`；执行中的只读动作重新观察后判断；可能已经发出的写动作恢复为 `unknown_outcome`，不得自动重放。

## 14. 数据与存储

### 14.1 SQLite 表

- `devices`：最近发现的设备元数据
- `tasks`：任务目标、约束、状态和预算
- `task_steps`：每轮决策与状态
- `tool_calls`：动作参数、风险、结果和耗时
- `observations`：前台应用、屏幕元数据与证据引用
- `artifacts`：文件路径、类型、哈希、大小和保留策略
- `confirmations`：风险确认请求与用户决定
- `audit_events`：不可变审计事件
- `settings`：非敏感配置引用

密钥不进入 SQLite 明文，使用操作系统 Keychain 保存。

ITER-0009 当前先落地最小持久化表：

- `schema_migrations`：记录已应用 migration。
- `tasks`：保存已完成 `TaskRun` JSON 快照和常用索引字段。
- `task_events`：保存紧凑 `TaskEvent` JSON 快照和 sequence。

后续正式异步任务队列、运行中任务恢复和复杂查询再扩展为更细粒度表结构。

### 14.2 Artifact Store

建议目录：

```text
data/
├── mobile-agent.db
└── artifacts/
    └── 2026/07/03/{task_id}/
        ├── observations/
        ├── screenshots/
        ├── ui-trees/
        └── report.json
```

Artifact 使用 SHA-256 校验，数据库保存相对路径。默认保留 7 天，可由用户调整或立即清理。

## 15. 安全设计

### 15.1 信任边界

- 模型输出：不可信
- Skill 参数：不可信，必须校验
- 设备返回内容：不可信，限制大小并安全解析
- 外部 MCP Client：不可信，必须认证和执行策略
- 桌面前端：不能直接访问系统命令

### 15.2 命令安全

- 仅允许预注册的可执行文件和固定命令模板。
- 所有参数通过类型模型构造。
- 不启用 shell，不接受重定向、管道或命令替换。
- 对设备 ID、包名、坐标、文本长度和文件路径做白名单校验。
- 进程设置超时、输出上限和取消机制。

### 15.3 Local API 安全

- 只监听 loopback。
- Runtime 启动生成短期随机令牌。
- Tauri 通过受控 IPC 获得令牌。
- 校验 Origin，拒绝普通网页跨站调用。
- 日志中不记录 Authorization、模型密钥和完整敏感输入。

### 15.4 隐私

- 截图和 UI 树默认仅本地保存。
- 调用云模型前明确提示屏幕内容可能离开本机。
- 支持本地模型模式和关闭截图上传。
- 后续增加敏感区域识别与截图脱敏。

## 16. 错误模型

统一错误码示例：

```text
DEVICE_NOT_FOUND
DEVICE_OFFLINE
DEVICE_UNAUTHORIZED
DEVICE_LOCKED
CAPABILITY_UNAVAILABLE
TARGET_NOT_FOUND
TARGET_AMBIGUOUS
ACTION_REJECTED_BY_POLICY
CONFIRMATION_REQUIRED
ACTION_TIMEOUT
ACTION_OUTCOME_UNKNOWN
OBSERVATION_FAILED
MODEL_UNAVAILABLE
MODEL_OUTPUT_INVALID
NO_PROGRESS
TASK_CANCELLED
INTERNAL_ERROR
```

错误对象包含：

- `code`
- 用户可理解的 `message`
- 调试用 `details`
- `retryable`
- `suggested_action`
- 关联的 `task_id`、`step_id` 和 `artifact_refs`

## 17. 可观察性

### 17.1 结构化日志

每条日志至少包含：

- timestamp
- level
- component
- correlation_id
- task_id / step_id / device_id
- event
- duration_ms
- error_code

不得记录模型密钥、授权令牌和未经脱敏的敏感文本。

### 17.2 指标

V1 本地统计：

- task success rate
- action success rate
- observation latency
- model latency
- device command latency
- steps per task
- no-progress count
- human intervention rate

默认不上传遥测；后续遥测必须显式选择加入。

## 18. 测试方案

### 18.1 单元测试

- Schema 和状态转换
- Policy Engine
- selector 解析和 UI 节点匹配
- ADB 输出解析
- 错误映射
- Agent 防循环逻辑

### 18.2 Contract 测试

- Adapter Interface
- Tool Schema 与 Handler
- Skill Manifest 与 Handler
- REST/MCP 输入输出一致性
- Python 与 TypeScript 生成类型一致性

### 18.3 集成测试

使用可替换的 Fake Adapter 测试完整任务流程，不依赖真实设备。Fake Adapter 根据动作返回预设 Observation 序列，可复现：

- 正常导航
- 元素不存在
- 权限弹窗
- 设备断开
- 页面无变化
- 动作超时

### 18.4 真机端到端测试

以固定 Android Emulator 镜像为基准环境，至少覆盖：

- 设备发现
- 截图和 UI 树
- 打开设置
- 进入指定设置页面
- Back/Home
- 中途断连
- 任务暂停与取消

真机覆盖至少一台主流 Android 设备，验证厂商差异。

### 18.5 Agent 评测

建立版本化任务集，每个任务包含：

- 初始设备快照或初始化脚本
- 自然语言目标
- 禁止动作
- 成功判定器
- 最大步骤和时间

模型或 Prompt 变更必须回归任务成功率、步数、耗时和违规动作数。

## 19. 打包与运行

### 19.1 开发环境

```text
Desktop Dev Server
        ↓
Python Runtime（独立进程）
        ↓
系统已安装的 adb 或配置路径
```

### 19.2 发布包

Tauri 打包桌面应用和编译后的 Runtime sidecar。Android Platform Tools 初期优先使用用户已安装版本，并在首次启动时完成诊断；后续评估随应用分发的许可、更新和多架构成本。

Runtime 数据目录使用系统标准 Application Support 路径，不写入应用安装目录。

## 20. 开发里程碑

### M0：工程骨架

- 建立 Monorepo
- Contracts 与类型生成
- Runtime 健康检查
- Tauri 启动 sidecar 并完成认证
- SQLite 迁移框架

### M1：确定性 Android Gateway

- ADB Runner
- 设备发现与 inspect
- Observation 采集
- 基础输入动作
- Fake Adapter 与 Adapter contract tests

验收：无需模型即可在桌面端手动打开设置并看到操作前后截图。

### M2：Task / Tool / Skill Runtime

- Tool Registry
- Skill Registry
- Task 状态机
- Policy Engine
- Evidence Store
- REST 和 WebSocket

验收：通过 `open_app` Skill 完成设置应用启动与验证。

### M3：Agent Loop

- Model Provider
- 结构化动作输出
- Observe–Act–Verify
- 防循环、暂停、取消和人工接管
- 标杆任务评测集

验收：自然语言完成简单设置页面导航，失败时产生可解释报告。

### M4：AI Native 接口

- MCP stdio Server
- CLI
- Skill 列表与调用文档
- 外部 Agent 示例

验收：外部 AI Agent 能发现设备、调用 `mobile_execute_task` 并查询最终结果。

## 21. 关键风险与应对

### UI 树缺失或不完整

自绘控件、游戏和部分 WebView 可能缺少可用语义。V1 明确报告能力不足；后续增加 OCR、视觉 grounding 和 Appium Provider。

### ADB 输入兼容性

不同系统和输入法可能影响文本输入。V1 收紧字符集并显式报错；后续增加设备端输入法 helper。

### 模型误判任务完成

完成状态必须由规则验证器、前台应用、UI 状态或用户确认支持，不能仅采信模型文本。

### 平台抽象过度

统一的是目标和 capability，不强行统一平台不具备的能力。Adapter 可以返回 `CAPABILITY_UNAVAILABLE` 和平台限制说明。

### 桌面打包复杂

开发阶段先让 Runtime 独立可运行，待功能稳定后再固化 sidecar 打包。Runtime 与前端通过版本化 API 协商兼容性。

## 22. V1 技术完成定义

满足以下条件视为 V1 技术闭环完成：

- 桌面端能够启动并认证本地 Runtime。
- Runtime 能稳定识别一台 Android 设备。
- 能采集截图、UI 树和前台应用并生成 Observation。
- 所有动作只通过注册 Tool 进入 Device Adapter。
- `open_app` 确定性 Skill 能执行并验证。
- `execute_mobile_task` 能完成标杆自然语言任务。
- 任务可暂停、取消并在断连时安全停止。
- 每个动作具有前后 Observation、结果和审计记录。
- MCP Client 能调用目标级 Skills，且不能绕过 Policy Engine。
- 禁止动作和未经确认的高风险动作无法到达设备执行层。
