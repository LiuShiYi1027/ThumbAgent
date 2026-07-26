# Mobile Agent

面向 AI Agent 的本地优先、跨平台移动设备 Skills 平台。

## 当前进展

项目已完成 ITER-0045 Scoped App Removal：独立确认数据删除影响后，安全卸载非系统应用并验证包缺失。
使用 Python 3.11+：

```bash
make check
make run
```

Runtime 默认监听 `127.0.0.1:8765`，提供 `/v1/health`、`/v1/devices` 和 `POST /v1/devices/{device_id}/observe`。

## MCP Skills 开发者预览

在 macOS + Codex 桌面端进行本地真机验收时，可以使用一键脚本：

```bash
./scripts/run-mcp-preview.zsh
```

首次运行时，脚本会提示输入模型 Key，并将模型 Key 与稳定的本地 Runtime token 分别保存到 macOS
登录 Keychain；后续启动不会再次询问。脚本会安全停止占用目标端口的旧
`mobile_agent.api.server`、复用未变化的 MCP 注册并启动新 Runtime。Codex/ChatGPT 已运行时无需
关闭或重新打开。只有首次注册、显式 `--refresh-mcp`、MCP 配置或 Tool Catalog 发生变化时，
运行中的 Codex 需要重启一次并新建任务，以刷新缓存的 MCP 环境；普通 Runtime 重启不需要。

模型 Key 只进入 Keychain 和 Runtime 进程环境，不写入仓库或脚本输出。脚本保持前台运行，按
`Ctrl+C` 停止 Runtime。仅检查 Python、ADB、Codex 和模型配置路径而不读取密钥或修改 MCP 配置时，
使用：

```bash
./scripts/run-mcp-preview.zsh --check
```

需要强制刷新 MCP 注册或删除预览 Secret 时：

```bash
./scripts/run-mcp-preview.zsh --refresh-mcp
./scripts/run-mcp-preview.zsh --forget-secrets
```

刷新注册不会轮换 Keychain 中的 token。若目标端口被其他程序占用，脚本会拒绝误杀；它只自动停止
命令行明确属于 `mobile_agent.api.server` 的进程。

为了让 Web、CLI 和 MCP 共享同一个 Runtime，请使用显式本地 token 启动服务：

```bash
MOBILE_AGENT_API_TOKEN=<local-random-token> \
MOBILE_AGENT_ADB_PATH=/usr/local/platform-tools/adb \
make run
```

然后在 MCP Host 中配置 stdio Server，使用同一个 token。示例见
[mcp-server.example.json](./docs/examples/mcp-server.example.json)。MCP Host 实际启动的命令为：

```bash
PYTHONPATH=runtime \
MOBILE_AGENT_API_TOKEN=<same-local-random-token> \
python3.11 -m mobile_agent.mcp
```

MCP 提供目标级 Tools，覆盖就绪诊断、设备与已安装应用检查、应用生命周期、Agent 异步任务、
任务查询/取消、脱敏日志、聚合性能快照、诊断证据包和性能比较。它不暴露 ADB、任意 Shell 或
`input.tap` 等原子输入 Tool。需要确认的动作只有在 MCP Host 已向用户展示参数和影响并获得确认后，
才允许传入 `confirmed=true`。

启动后可查看统一就绪诊断：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.runtime_diagnose
```

`GET /v1/readiness` 与 Web UI 会展示 Android Gateway、设备连接/授权、Session、Lease 占用和
修复建议。ADB 未安装或路径错误时 Runtime 仍会启动诊断界面，不再直接因 `ADB_NOT_FOUND` 退出。

查看单台设备的当前能力、风险、确认要求和限制：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_inspect <device_id>
```

MCP 还提供只读的 `mobile_list_apps` 与 `mobile_inspect_app`，用于有界列出应用标识和查询单应用的
版本、安装来源与启用状态。它们不返回 APK 路径、签名、权限或原始 `dumpsys`，也不会启动或修改应用。

本地 APK 安装只接受 `<data-dir>/apks` 目录中的单个 `.apk`。外部 Agent 必须先调用
`mobile_prepare_apk_install` 获取包含文件名、大小、SHA-256、Manifest package id 和替换影响的短期
Approval；MCP Host 向用户展示该摘要并取得明确确认后，才能调用 `mobile_install_apk`。Approval
十分钟过期且默认只能使用一次。Runtime 不下载 URL，不接受 split APK 或任意 ADB 参数。

应用卸载使用独立的 `mobile_prepare_app_uninstall` → `mobile_uninstall_app` 两阶段流程。Prepare
只读返回应用版本、系统应用判定和数据删除影响；系统应用或属性未知的应用直接拒绝。用户对该摘要
重新明确确认后才能提交异步卸载任务。失败或结果未知时不得自动重试。

应用生命周期提供 `mobile_inspect_app_state`、`mobile_launch_app` 和 `mobile_stop_app`。状态检查
只返回进程是否存在、是否前台和 stopped flag；启动、停止返回异步 task_id，停止非系统应用前必须
明确确认。永久清除应用数据必须先调用 `mobile_prepare_app_data_clear`，展示包名、版本和数据删除
影响并获得一次新的明确确认，再调用 `mobile_clear_app_data`。应用数据清除不会卸载应用，失败或
unknown outcome 不得自动重试。

显式确认后采集最近日志快照（需传入 Runtime 启动时生成的本地 API token）：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_logs_collect \
  <device_id> --max-lines 500 --minimum-level info --confirm --token <runtime-token>
```

日志会先脱敏，再保存为最大 1 MiB 的本地 Artifact；CLI 和 REST 不返回日志正文。
添加 `--async-task` 可立即获得 task_id，并使用统一执行状态、事件、取消与任务报告：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_logs_collect \
  <device_id> --confirm --async-task --deadline-seconds 60 --token <runtime-token>
```

采集聚合 CPU、内存、电池温度与系统负载快照：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_performance_snapshot \
  <device_id> --async-task --deadline-seconds 90 --token <runtime-token>
```

性能 Artifact 只包含聚合 JSON 指标，不保存 dumpsys 原文、进程名或应用明细。

一次性采集截图、UI Tree、脱敏日志、聚合性能和可选应用状态，并生成带 SHA-256 清单的本地 ZIP：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.diagnostic_bundle_collect \
  <device_id> --app-id <package-id> --max-log-lines 500 \
  --minimum-log-level info --confirm --token <runtime-token>
```

诊断包属于 Medium 风险，必须明确确认。CLI、Web、REST 与 MCP 仅返回 Artifact 元数据和安全摘要，
不内联截图、UI Tree、日志或 ZIP 内容；包内文件名固定，总大小不超过 24 MiB，且不会上传或外发。

比较同一设备上两条已完成的性能快照任务：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_performance_compare \
  <baseline_task_id> <candidate_task_id> --token <runtime-token>
```

Web 任务报告也可以将一条成功快照设为基线，再选择另一条快照进行比较。比较结果只表示两点样本的
数值方向和稳定阈值，不自动判定因果关系或性能回退。

如果 `adb` 不在 `PATH` 中，可以显式配置：

```bash
MOBILE_AGENT_ADB_PATH=/usr/local/platform-tools/adb
```

ITER-0003 增加 `GET /v1/tools`、`POST /v1/tools/{tool_id}/invoke` 和 `POST /v1/skills/app.open/invoke`。`input.tap` 属于 Medium 风险，默认需要明确确认。

ITER-0004 增加安全 UI hierarchy 解析、语义 Selector、`input.tap_element` 和 `POST /v1/skills/settings.navigate/invoke`。语义点击属于 Medium 风险，匹配不唯一时拒绝执行。

ITER-0005 增加受策略约束的 `input.swipe`、`input.text`、有界语义滚动查找和 `POST /v1/skills/settings.scroll_navigate/invoke`。滚动和输入均属于 Medium 风险，默认需要明确确认；密码、验证码、支付、账号安全和自动提交场景不在本迭代范围内。

ITER-0006 增加最小 Task Runner、`TaskRun` 证据报告和预览型同步端点 `POST /v1/tasks/settings.scroll_navigate/run`。该端点只包装已有 `settings.scroll_navigate` Skill，不替代后续异步任务队列设计。

ITER-0007 增加进程内 Task Store、`TaskEvent` 和查询端点 `GET /v1/tasks/{task_id}`、`GET /v1/tasks/{task_id}/events`。该 Store 仅在当前 Runtime 进程生命周期内有效，尚不提供重启恢复。

ITER-0008 增加第一版 CLI 任务报告视图，可将 `TaskRun` 与 `TaskEvent` 渲染为用户可读报告：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.task_report <task_id>
```

该命令从本地 Runtime API 查询任务和事件。

ITER-0009 增加 SQLite Task Store，默认将任务和事件保存到 `<data-dir>/mobile-agent.db`。设置 `MOBILE_AGENT_DATA_DIR` 时，数据库位于该目录下；否则使用平台默认本地数据目录。

ITER-0010 增加历史任务列表：

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.task_list --limit 20
```

列表展示最近任务摘要，可复制其中的 `task_id` 后用 `task_report` 查看详情。

ITER-0011 增加本地 Web UI。启动 Runtime 后打开：

```text
http://127.0.0.1:8765/ui
```

即可查看任务历史和任务报告详情。

ITER-0012 在 Web UI 中增加“运行安全 Demo”按钮。该按钮会选择在线 Android 设备，运行固定任务：打开系统设置并进入显示/亮度页面。POST 请求仍使用本地 Runtime token，并只允许同源 loopback 页面触发。

ITER-0013 增加模型接入前的 Agent Loop Preview：`POST /v1/tasks/agent.run`。该端点使用 deterministic Planner 生成受约束决策，目前只支持安全示范目标“进入系统设置的显示/亮度页面”，并将观察摘要、Planner 决策、Skill 执行结果和证据写入任务报告。

ITER-0014 在 Web UI 中增加自然语言任务输入框和“运行 Agent Preview”按钮。页面会调用 `POST /v1/tasks/agent.run`，并在任务返回后刷新历史列表、打开任务报告。

ITER-0015 增加 LLM Planner 的内部预览契约和 `MockLLMPlanner`。模型式输出必须先经过结构化解析与字段校验，再由 Agent Runner 的 Skill allowlist 二次校验；本迭代不调用真实模型服务、不读取模型密钥。

ITER-0016 增加默认关闭的 OpenAI-compatible Planner Provider 预览。Provider 能构造 chat-completions 风格请求、通过可注入 transport 解析结构化响应，并复用 ITER-0015 的 Planner 输出校验；默认 Runtime 不启用真实 Provider，测试不依赖网络或模型密钥。

ITER-0017 增加模型 Provider 配置门：默认配置仍返回 `RuleBasedPlanner`；只有显式启用 `openai_compatible`、提供 `base_url`、`model` 和 `api_key_ref`，并通过注入的 `SecretResolver` 解析密钥后，才会构造 OpenAI-compatible Planner。本迭代不接入默认 Runtime、不读取真实密钥。

ITER-0018 增加模型 Provider 只读状态入口：`GET /v1/model-provider/status` 和 Web UI 中的“模型 Provider”状态面板。状态只展示是否启用、provider、model 和是否配置密钥引用，不返回真实密钥或 `api_key_ref` 原文；默认 Runtime 仍不启用真实模型。

ITER-0019 增加本地模型配置读取：Runtime 启动时会读取 `<data-dir>/model-provider.json` 或 `MOBILE_AGENT_MODEL_CONFIG` 指定文件，并允许 `MOBILE_AGENT_MODEL_*` 环境变量覆盖配置字段。配置文件只保存 `api_key_ref`，开发预览 SecretResolver 仅解析 `env:MOBILE_AGENT_MODEL_SECRET_*` 引用；默认 Agent Runner 仍不调用真实模型。

ITER-0020 将模型 Planner 受控接入默认 Runtime：配置关闭时继续使用规则 Planner；配置开启且密钥引用可解析时使用 OpenAI-compatible Planner；配置开启但不可用时，Agent 任务以 `MODEL_UNAVAILABLE` 明确失败，不静默退回规则 Planner。模型输出仍需经过结构化解析、Skill allowlist、Policy Engine 和 Device Gateway。

ITER-0021 增强 Web UI 模型 Provider 状态卡片：区分未启用、已接入、配置不可用和配置已读取，并在不可用时提示检查配置文件、`MOBILE_AGENT_MODEL_CONFIG` 与 `MOBILE_AGENT_MODEL_SECRET_*`。仓库提供配置示例：[model-provider.example.json](./docs/examples/model-provider.example.json)。

ITER-0022 将 Agent Preview 从“一轮模型决策调用大 Skill”升级为“多轮模型决策 + 原子 Tool 执行 + 每轮重新观察”。Planner 可输出 `run_tool`、`finish`，Runtime 只允许白名单 Tool，并在 `finish` 时通过 UI Selector 做确定性验证；旧 `run_skill` 路径仍保留兼容。

ITER-0023 将 Agent 每轮报告中的 `AgentObservationSummary`、`AgentDecision` 和 `AgentStepResult` 提升为公共 JSON Schema，并更新 `TaskRun` Schema 正式支持 `agent.run`。桌面端、CLI 和未来外部 Agent 可以稳定消费多轮 Observe–Plan–Act 报告。

ITER-0024 增加 Agent 动作进展反馈：Runtime 比较 Tool 前后的前台应用与 UI tree，将 `changed` / `unchanged` 反馈给下一轮模型，并阻止相同无进展动作再次派发。Web 报告同步展示实际 Tool、参数和页面进展。

ITER-0025 优化模型侧 Observation：过滤无语义布局节点，优先保留可见文本和可操作节点，补充摘要截断元数据，并在 UI 文本进入模型 Prompt 与任务摘要前脱敏常见手机号、邮箱和长数字标识符。

ITER-0026 新增严格 Agent ToolCall Contract、模型无效参数的一次有界修复和失败轮次证据保留。真机已完成“进入显示和亮度”的多轮模型闭环。

ITER-0027 建立目标驱动的在线 Agent 评测基础：真实模型每次都面对当前设备界面重新规划，评测只约束目标、最终状态、禁用 Tool 和轮次预算，不比较固定动作路径。已完成的 `agent.run` 可通过 `POST /v1/tasks/{task_id}/evaluate` 评测，场景示例位于 [agent-evaluation-scenario.example.json](./docs/examples/agent-evaluation-scenario.example.json)。

ITER-0042 将多个路径无关场景组织为版本化 Suite。先通过 Web 或 MCP 分别执行 Suite 中的目标，
再把已完成的 task_id 交给只读聚合 CLI；该命令只调用已有评测 API，不会提交或重放设备动作：

```bash
./scripts/report-mcp-evaluation.zsh \
  --suite evaluations/android-settings-smoke-v1.json \
  --task settings.bluetooth.v1=task_<id> \
  --task settings.display-brightness.v1=task_<id> \
  --task settings.battery.v1=task_<id>
```

报告展示总成功率、逐场景成功率、耗时 p50/p95、平均轮次和 Tool 数，以及 Provider 重试、
`NO_PROGRESS`、`MODEL_UNAVAILABLE` 和策略违规统计。Suite 定义目标与独立成功条件，不包含固定动作路径。
脚本只读取 Codex 中已注册的 `mobile-agent` 本地连接信息，不打印 token，也不提交设备任务。

ITER-0028 强化可靠性：无副作用的目标定位和 `finish` 验证失败可以作为 failed round 反馈模型继续规划；`finish` 可组合前台 app/activity 和 UI Selector；顶部系统区与底部手势区点击会在派发前被拦截。Provider 超时、HTTP、连接和响应格式错误会分类记录，并对 retryable 模型请求最多重试一次；无效 Selector 只展示字段级脱敏诊断。
模型省略非安全关键的 `reason` 时，Runtime 会生成固定审计说明，不会为此发起额外模型修复请求；Tool、Selector、Policy 和完成条件仍保持严格校验。

ITER-0029 增加调用方可选的 Runtime-owned 成功条件。`POST /v1/tasks/agent.run` 可接收
`acceptance`，使用前台 app id、Activity 和唯一 UI Selector 的 all-of 语义验证模型发出的
`finish`；路径仍由模型根据实时 Observation 动态规划。任务报告会持久化并展示
`goal_acceptance` 与 `completion_source`。请求示例位于
[agent-run-runtime-acceptance.example.json](./docs/examples/agent-run-runtime-acceptance.example.json)。

ITER-0030 增加两阶段目标编译：`POST /v1/goals/compile` 将短自然语言目标转换为可审阅的
`AgentGoalSpec` 草案，包含增强后的执行目标、假设、置信度和可选成功条件。模型草案必须由
用户显式确认后才能传入 `agent.run`；任务仍由模型根据实时 Observation 动态规划，不生成固定
动作路径。示例见 [agent-goal-spec.example.json](./docs/examples/agent-goal-spec.example.json)。

ITER-0031 增加异步 Agent 执行：`POST /v1/tasks/agent.run/async` 立即返回 `202 Accepted` 和
task_id，`GET /v1/task-executions/{task_id}` 与 `/events` 提供持久化状态和逐轮事件，
`POST /v1/task-executions/{task_id}/cancel` 请求在安全边界取消。异步创建支持
`Idempotency-Key`；原同步 `POST /v1/tasks/agent.run` 保持兼容。本地 Web UI 默认使用异步入口。

ITER-0032 为 Runtime 公开写入口增加同设备独占租约，并为同步/异步 `agent.run` 增加可选
`deadline_seconds`（默认 600 秒，范围 1–1800）。设备被其他任务占用时返回 `DEVICE_LOCKED`；
任务在安全边界超过预算后以 `timed_out/TASK_DEADLINE_EXCEEDED` 结束，已完成动作的证据仍保留。

ITER-0033 为同一数据目录增加 Runtime 单实例锁，并为每段连续在线设备连接生成 `session_id`。
任务与租约绑定当前 Session；设备断开或重连后，旧任务以 `DEVICE_SESSION_CHANGED` 停止，不会把
后续动作发送到新连接。Device、TaskExecution、TaskRun 与 Web/CLI 报告均展示会话标识。

ITER-0034 增加统一 Runtime/Device Readiness：Web 和 CLI 使用同一只读 Contract 解释 ADB、设备
连接与授权、Session 和 Lease 状态；只有 `ready` 设备可以从 Web 发起任务。ADB 缺失时 Runtime
进入诊断模式并提供修复建议，不自动安装工具或修改设备配置。

ITER-0035 增加 Device Inspection 和 Capability Catalog。Web 中可点击设备查看八项基础 V1 能力；
`GET /v1/devices/{device_id}/inspection` 与 CLI 展示当前可用性、风险、幂等性、验证要求、关联
Tools 和限制。Inspection 只读取设备发现与 Lease，不截图、不读取 UI、不执行动作。

ITER-0036 增加第一个工程诊断 Skill：`POST /v1/skills/device.logs.collect/invoke`。Android Adapter
只接受有界行数和固定日志级别，使用固定 logcat 参数采集快照；Skill 要求 Medium 风险显式确认，
并在本地脱敏后生成 `device_log` Artifact。Web 和 CLI 只展示 Artifact 元数据。持续流式采集、任意
logcat filter 和日志上传不在本迭代范围内。

ITER-0037 将日志采集接入统一异步任务链路：
`POST /v1/tasks/device.logs.collect/async` 返回 `202 Accepted`，并复用 TaskExecution 状态、增量
事件、Idempotency-Key、取消、Deadline、Device Session、Lease 和持久化 TaskRun 报告。Web
日志按钮默认异步提交；同步 Skill 端点继续保留。执行器只允许代码内登记的 Agent 与日志任务类型，
客户端不能提交任意 handler。

ITER-0038 增加 `device.performance.snapshot`：Android Adapter 通过固定只读命令采集总 CPU、
Total/Free RAM、电池电量/温度、uptime 和 load average，只将规范化数值写入本地 JSON Artifact。
同步 Skill、异步 Task、Web 和 CLI 共用同一 Contract；不提供应用/PID 明细和持续采样。

ITER-0039 增加 `POST /v1/performance-comparisons`，以同一设备上两个成功的性能快照 TaskRun 为
输入，计算 CPU、内存、电量、温度和负载的两点差值与阈值趋势。比较完全在本地读取结构化任务证据，
不访问设备、模型或原始 dumpsys；Web 和 CLI 明确提示两点样本不能单独证明因果或性能回退。

ITER-0040 增加 MCP `2025-11-25` stdio 开发者预览。MCP 子进程只调用已启动 Runtime 的固定
localhost REST API，因此与 Web 共享任务、Session、Lease 和 Policy；所有耗时能力异步返回
Mobile Agent task_id。Tool 输入来自公共 Contract，调用前经过严格校验和限流，领域错误以
structuredContent 返回。暂不实现 MCP Tasks、远程传输、Resources 或 Prompts。

ITER-0047 增加 `device.diagnostics.bundle`。一次已确认的异步任务在同一 Device Session 与 Lease
中组合 Observation、脱敏日志、聚合性能和可选应用状态，生成固定内容的本地 ZIP。Manifest 记录
四个来源 Artifact 的名称、大小和 SHA-256；Runtime 在发布诊断包前重新校验来源完整性和 ZIP
文件集合，失败时保留已经完成的安全 Artifact 引用。

真实 Provider 若持续在默认 30 秒预算附近完成响应，可在本地配置中将
`timeout_seconds` 调高到 60（允许范围 1–120），或通过
`MOBILE_AGENT_MODEL_TIMEOUT_SECONDS=60` 覆盖。超时重试可能产生额外模型调用，任务报告会展示重试次数。

## 产品文档

- [产品定位](./docs/product/positioning.md)
- [第一版产品方案](./docs/product/solution-v1.md)
- [V1 技术方案](./docs/architecture/technical-design-v1.md)

## 工程规范

- [Agent 开发入口](./AGENTS.md)
- [贡献指南](./CONTRIBUTING.md)
- [文档与迭代规范](./docs/documentation-guide.md)
- [工程开发规范](./docs/engineering/development.md)
- [Contract 与 API 演进规范](./docs/engineering/contract-versioning.md)
- [Capability 模型](./docs/architecture/capability-model.md)
- [Skill 开发规范](./docs/engineering/skill-development.md)
- [可靠性与执行语义](./docs/architecture/reliability-model.md)
- [数据与迁移规范](./docs/engineering/data-migrations.md)
- [错误与诊断规范](./docs/engineering/error-handling.md)
- [架构边界](./docs/architecture/rules.md)
- [测试规范](./docs/engineering/testing.md)
- [安全规范](./docs/engineering/security.md)
- [多 Agent 协作规范](./docs/engineering/agent-collaboration.md)
- [架构决策记录](./docs/adr/README.md)
- [迭代索引](./docs/iterations/README.md)
