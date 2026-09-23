# ThumbAgent 当前架构图（实现态）

> 状态：Active
> 更新日期：2026-09-08（对照实现核对生成，非目标态）
> 范围：V1 + Agent 内核（ITER-0061）+ DSL 复合 Skill（ITER-0062/0063）+ 可靠性批次（ITER-0064）+ 稳定性报告（ITER-0065）

## 总体分层

```mermaid
flowchart TB
    subgraph Clients["Clients / Interfaces（客户端层）"]
        Desktop["Desktop Workbench<br/>Tauri 2 + React（mono 主题）<br/>Rust sidecar：拉起 Runtime、令牌内存持有、<br/>POST 白名单桥、Keychain 密钥注入"]
        CLI["CLI<br/>（task_report / logs / performance /<br/>cleanup / evaluate… 纯 HTTP）"]
        MCPClient["外部 Agent<br/>Codex 等"]
        WebUI["内嵌 Web UI<br/>/ui?token=（H1 修复后需令牌）"]
    end

    subgraph Interface["Interface Layer（接口适配层）"]
        REST["REST API（api/server.py）<br/>127.0.0.1 · Bearer compare_digest · Host 回环校验<br/>严格未知字段 · 统一七字段错误信封 · 幂等键去重<br/>事件走轮询（无 WebSocket）"]
        MCP["MCP stdio Server<br/>薄适配器：契约驱动入参校验 + 限流<br/>固定目标级工具目录"]
    end

    subgraph Runtime["Mobile Agent Runtime（应用层，Python 3.11 asyncio）"]
        direction TB
        TaskEngine["Task Engine（tasks/execution.py）<br/>单工作线程 · 持久化 TaskExecution<br/>协作式暂停/接管/取消（步骤边界探针）<br/>DeviceLease 独占 · deadline 熔断 · Session 复核<br/>取消在模型调用窗口 <2s 生效（ITER-0064 M4）"]
        AgentRunner["Agent Runner（agent/runner.py）<br/>Observe–Plan–Act 循环 · NO_PROGRESS 检测<br/>导航捷径（谓词守卫 M6）· 瞬时观察重试<br/>scratchpad 跨轮记忆 · finish 携带 answer（ITER-0061）"]
        Skills["Skills<br/>内置硬编码（open_app / unicode_input /<br/>app.install·uninstall·clear 两阶段高危 …）<br/>+ DSL 复合 Skill 解释器（ITER-0062/63）<br/>白名单观察 Skill 引用 · 风险强制派生 max"]
        GoalCompiler["GoalCompiler<br/>目标编译草案（需确认）"]
        Evaluator["AgentEvaluator<br/>在线评测 + Suite 聚合"]
        TaskEngine --> AgentRunner
        AgentRunner --> Skills
    end

    subgraph Domain["Domain / Policy / Contracts（领域层）"]
        Contracts["contracts/schemas/<br/>JSON Schema 唯一真源 → 生成 TS 类型<br/>CI 漂移门禁"]
        Policy["PolicyEngine<br/>deny-by-default · Low/Medium/High/Prohibited<br/>权限弹窗上下文守卫（ADR-0020）"]
        Catalog["CapabilityCatalog<br/>能力风险/幂等性/验证要求元数据真源"]
        Policy -.读元数据.- Catalog
    end

    subgraph Persistence["Persistence（本地持久化）"]
        SQLite["SQLite（mobile-agent.db）<br/>tasks · task_executions · custom_skills<br/>skill_audit · 终态不可变防线"]
        Artifacts["ArtifactStore<br/>截图/UI树/日志/性能 · 按 kind 大小上限<br/>SHA-256 清单 · 保留期 + 两阶段清理"]
        Keychain["macOS Keychain<br/>模型 API Key（不落盘）"]
        Config["model-provider.json<br/>只存密钥引用 0600 原子写"]
    end

    subgraph Gateway["Device Gateway"]
        DeviceGW["Device Registry · Session Manager · DeviceLease<br/>单实例文件锁 · Session 变更即 TASK_INTERRUPTED"]
    end

    subgraph Adapters["Platform Adapters"]
        Android["AndroidDeviceAdapter<br/>固定 adb argv · 无 shell · 参数白名单<br/>UIAutomator dump · 截图 · 输入 · 包管理"]
        Fake["FakeDeviceAdapter<br/>（测试）"]
        Unavailable["UnavailableDeviceAdapter<br/>（ADB 缺失时拒绝一切设备访问）"]
        HelperIME["Unicode Helper IME APK<br/>helpers/unicode-ime（CJK 输入，UTF-7 管道）"]
    end

    subgraph External["外部服务"]
        LLM["模型 Provider（OpenAI 兼容）<br/>LM Studio 本地 / SiliconFlow 云端<br/>默认关闭 · 显式配置门"]
    end

    Desktop -->|IPC（白名单命令）| REST
    CLI -->|HTTP + 稳定幂等键| REST
    WebUI -->|HTTP| REST
    MCPClient -->|stdio| MCP
    MCP -->|loopback HTTP| REST

    REST --> Runtime
    MCP -.不直连.- Gateway

    Runtime --> Domain
    Skills --> Policy
    Runtime --> Persistence
    AgentRunner -->|OpenAI 兼容请求<br/>输出视为不可信：结构化解析+allowlist 二次校验| LLM
    LLM -.密钥由 Keychain 注入子进程环境.- AgentRunner

    Runtime --> Gateway
    Gateway --> Android
    Android -->|ADB（USB/网络）| Device[("📱 Android 真机/模拟器")]
    Android -.安装/切换/恢复.- HelperIME
    HelperIME -.作用于.- Device
```

## 信任边界与关键防线

```mermaid
flowchart LR
    subgraph 不可信["不可信域"]
        ModelOut["模型输出<br/>（JSON 文本）"]
        DSLDoc["DSL 文档<br/>（用户/第三方数据）"]
    end
    subgraph 防线["防线"]
        P1["结构化解析 +<br/>AgentDecision 校验"]
        P2["Tool/Skill allowlist<br/>二次校验"]
        P3["Schema → Capability →<br/>Policy 三重校验"]
        P4["高危两阶段 Approval<br/>（设备+内容指纹绑定）"]
    end
    subgraph 可信["可信执行域"]
        Tools["ToolRuntime<br/>Observe-Act-Verify 管线"]
    end
    ModelOut --> P1 --> P2 --> P3
    DSLDoc -->|解释器 preflight<br/>白名单/风险派生| P3
    P3 --> P4 --> Tools
```

## 关键数据流（一次 Agent 任务）

```mermaid
sequenceDiagram
    participant U as 用户（Desktop）
    participant API as REST API
    participant TE as Task Engine
    participant AR as Agent Runner
    participant TR as ToolRuntime
    participant D as Android 设备

    U->>API: POST /v1/tasks/agent.run/async（幂等键）
    API->>TE: 排队（持久化 queued）
    TE->>TE: 取得 DeviceLease + Session + deadline
    loop 每轮（≤ max_rounds，≤ deadline）
        AR->>TR: observe（截图+UI树，瞬时重试≤3）
        TR->>D: uiautomator dump / screencap
        AR->>AR: 语义压缩+脱敏 → Planner decide<br/>（to_thread，探针轮询取消/暂停）
        AR->>TR: run_tool/run_skill（allowlist+Policy）
        TR->>D: 固定 argv 动作
        TR->>TR: 后置观察验证 + ActionFeedback
        TE->>API: task.step_completed 事件<br/>（reason/scratchpad/截图引用）
    end
    AR->>TE: finish（acceptance 确定性验证 + answer）
    TE->>API: 终态 TaskRun（报告真源）
```

## 实现态与设计文档的差异（诚实标注）

| 设计文档说法 | 实现现状 |
| --- | --- |
| WebSocket 事件流 | 未实现；事件走 REST 轮询（1.2s 间隔） |
| `interfaces/mcp`、`interfaces/cli` 目录 | 实际在 `runtime/mobile_agent/mcp`、`runtime/mobile_agent/cli`（文档漂移已知） |
| iOS / 鸿蒙 Adapter 预留 | 仅有接口边界，无实现骨架 |
| Skill Manifest 声明与执行分离 | ITER-0062 前仅为测试夹具；DSL Skill 已真实解释执行，内置 Skill 仍为硬编码类 |

## 迭代脉络（架构视角）

```text
Runtime 骨架(0001) → 观察/动作/导航(0002-05) → 任务与证据(0006-12)
→ Agent 闭环与模型接入(0013-30) → 异步执行/租约/会话(0031-35)
→ 诊断能力(0036-39,43-48) → MCP 开放(0040) → 评测(0041-42,51)
→ 桌面工作台(0049-56) → 分发(0057) → 混合动作空间(0058-60)
→ Agent 内核(0061) → DSL Skill 平台(0062-63) → 可靠性(0064) → 报告呈现(0065)
```
