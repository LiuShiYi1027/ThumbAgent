# 迭代索引

> 状态：Active
> 更新日期：2026-08-02

| 迭代 | 名称 | 状态 | 目标 |
| --- | --- | --- | --- |
| [ITER-0001](./0001-runtime-foundation/plan.md) | Runtime Foundation | Completed | 建立可测试的 Runtime 骨架与 Android 设备发现能力 |
| [ITER-0002](./0002-standard-observation/plan.md) | Standard Observation | Completed | 生成截图、前台应用和 UI hierarchy 的本地观察快照 |
| [ITER-0003](./0003-basic-actions-open-app/plan.md) | Basic Actions & Open App | Completed | 建立受策略约束的动作闭环与第一个确定性 Skill |
| [ITER-0004](./0004-semantic-navigation/plan.md) | Semantic Navigation | Completed | 按 UI 语义安全定位元素并完成只读页面导航 |
| [ITER-0005](./0005-semantic-scroll-text-input/plan.md) | Semantic Scroll & Text Input | Completed | 有界滚动查找目标并在安全场景输入非敏感文本 |
| [ITER-0006](./0006-task-runner-evidence-report/plan.md) | Task Runner & Evidence Report | Completed | 将确定性 Skill 包装为可审计任务执行报告 |
| [ITER-0007](./0007-task-store-event-log/plan.md) | Task Store & Event Log | Completed | 在 Runtime 生命周期内查询任务记录和紧凑事件序列 |
| [ITER-0008](./0008-task-report-view/plan.md) | Task Report View | Completed | 将任务记录和事件渲染为用户可读 CLI 报告 |
| [ITER-0009](./0009-sqlite-task-store/plan.md) | SQLite Task Store | Completed | 将任务记录和事件持久化到本地 SQLite |
| [ITER-0010](./0010-task-history-list/plan.md) | Task History List | Completed | 列出最近任务摘要并作为报告入口 |
| [ITER-0011](./0011-local-web-task-ui/plan.md) | Local Web Task UI | Completed | 通过本地浏览器查看任务历史和报告详情 |
| [ITER-0012](./0012-web-demo-task-launcher/plan.md) | Web Demo Task Launcher | Completed | 从本地 Web UI 发起第一个受控 demo 任务 |
| [ITER-0013](./0013-agent-loop-preview/plan.md) | Agent Loop Preview | Completed | 建立不依赖真实 LLM 的 Observe–Plan–Act 任务循环骨架 |
| [ITER-0014](./0014-web-agent-task-input/plan.md) | Web Agent Task Input | Completed | 在本地 Web UI 中输入自然语言目标并发起 Agent Preview |
| [ITER-0015](./0015-llm-planner-contract/plan.md) | LLM Planner Contract | Completed | 定义模型 Planner 输出的内部预览契约与安全解析 |
| [ITER-0016](./0016-openai-compatible-planner-provider/plan.md) | OpenAI-Compatible Planner Provider Preview | Completed | 建立默认关闭、可测试的模型 Planner Provider 边界 |
| [ITER-0017](./0017-model-provider-configuration-gate/plan.md) | Model Provider Configuration Gate | Completed | 建立默认关闭、显式启用的模型 Provider 配置门 |
| [ITER-0018](./0018-model-provider-status-surface/plan.md) | Model Provider Status Surface | Completed | 在本地 Web UI 中只读展示模型 Provider 状态 |
| [ITER-0019](./0019-model-provider-local-config/plan.md) | Model Provider Local Config | Completed | 从本地配置加载模型 Provider 设置并保持密钥脱敏 |
| [ITER-0020](./0020-controlled-model-planner-runtime/plan.md) | Controlled Model Planner Runtime | Completed | 在显式模型配置可用时受控接入真实 Planner |
| [ITER-0021](./0021-model-provider-ux-guardrails/plan.md) | Model Provider UX Guardrails | Completed | 增强模型 Provider 状态展示与配置提示 |
| [ITER-0022](./0022-multi-round-tool-agent-preview/plan.md) | Multi-round Tool Agent Preview | Completed | 支持多轮模型决策、原子 Tool 执行和 finish 确定性验证 |
| [ITER-0023](./0023-agent-contract-step-report/plan.md) | Agent Contract & Step Report Formalization | Completed | 将 Agent 决策、观察摘要和每轮结果提升为公共 Contract |
| [ITER-0024](./0024-agent-no-progress-recovery/plan.md) | Agent No-progress Recovery | Completed | 检测无效动作、反馈模型并阻止相同动作循环 |
| [ITER-0025](./0025-observation-semantic-compaction/plan.md) | Observation Semantic Compaction & Redaction | Completed | 优先摘要可操作语义节点并脱敏模型侧 UI 文本 |
| [ITER-0026](./0026-agent-tool-contract-repair/plan.md) | Agent Tool Contract Repair & Failure Evidence | Completed | 严格校验模型 Tool 参数、有界修复无效输出并保留失败轮次证据 |
| [ITER-0027](./0027-live-goal-agent-evaluation/plan.md) | Live Goal-driven Agent Evaluation | Completed | 以真实模型动态规划的在线任务衡量目标达成、约束和效率，不回放固定路径 |
| [ITER-0028](./0028-agent-reliability-recovery/plan.md) | Agent Reliability & Recovery | Completed | 从验证歧义、安全点击和短暂 Provider 故障中有界恢复 |
| [ITER-0029](./0029-runtime-owned-goal-verification/plan.md) | Runtime-owned Goal Verification | Completed | 由调用方成功条件约束 Runtime 最终任务状态 |
| [ITER-0030](./0030-goal-understanding-compilation/plan.md) | Goal Understanding & Compilation | Completed | 将短自然语言目标编译为用户可确认的 GoalSpec 草案 |
| [ITER-0031](./0031-async-task-execution/plan.md) | Async Task Execution & Live Events | Completed | 异步提交 Agent 任务并持久化展示实时进度与取消状态 |
| [ITER-0032](./0032-device-lease-task-deadline/plan.md) | Device Lease & Task Deadline | Completed | 统一设备写租约并为 Agent 建立总执行时间预算 |
| [ITER-0033](./0033-runtime-instance-device-session/plan.md) | Runtime Single Instance & Device Session | Completed | 阻止双 Runtime 并将任务绑定到一次连续设备连接 |
| [ITER-0034](./0034-runtime-device-readiness/plan.md) | Runtime & Device Readiness | Completed | 在 Web/CLI 统一解释本地驱动、连接、授权、Session 与占用状态 |
| [ITER-0035](./0035-device-inspection-capability-catalog/plan.md) | Device Inspection & Capability Catalog | Completed | 展示单设备能力、风险、确认要求、限制与当前可用性 |
| [ITER-0036](./0036-android-logcat-bounded-capture/plan.md) | Android Logcat Bounded Capture | Completed | 以受控 Skill 采集、脱敏并保存有界 Android 日志 Artifact |
| [ITER-0037](./0037-async-diagnostic-task/plan.md) | Async Diagnostic Task | Completed | 将日志采集接入可取消、可查询、可恢复的统一异步任务链路 |
| [ITER-0038](./0038-android-performance-snapshot/plan.md) | Android Performance Snapshot | Completed | 采集并持久化不含进程明细的聚合 CPU、内存、电池和系统负载快照 |
| [ITER-0039](./0039-performance-baseline-comparison/plan.md) | Performance Baseline Comparison | Completed | 比较同一设备的两次聚合性能快照并展示可解释趋势 |
| [ITER-0040](./0040-mcp-skills-developer-preview/plan.md) | MCP Skills Developer Preview | Completed | 让外部 AI Agent 通过本地 MCP stdio 调用目标级 Mobile Skills |
| [ITER-0041](./0041-live-agent-reliability/plan.md) | Live Agent Reliability | Completed | 提升真实模型请求诊断与语义点击在系统安全区边缘的可靠性 |
| [ITER-0042](./0042-live-evaluation-baseline/plan.md) | Live Evaluation Baseline | Completed | 用版本化场景集和聚合指标建立真实 Agent 成功率基线 |
| [ITER-0043](./0043-app-inventory/plan.md) | App Inventory | Completed | 通过 REST 与 MCP 安全列出和检查 Android 已安装应用 |
| [ITER-0044](./0044-scoped-apk-install/plan.md) | Scoped APK Install | Completed | 通过范围绑定授权安全安装本地 APK 并验证结果 |
| [ITER-0045](./0045-scoped-app-removal/plan.md) | Scoped App Removal | Completed | 独立确认数据删除影响后安全卸载非系统应用并验证包缺失 |
| [ITER-0046](./0046-application-lifecycle-management/plan.md) | Application Lifecycle Management | Completed | 检查、启动、停止并安全清除非系统应用数据 |
| [ITER-0047](./0047-diagnostic-evidence-bundle/plan.md) | Diagnostic Evidence Bundle | Completed | 一次受控调用采集并封装本地工程诊断证据 |
| [ITER-0048](./0048-local-data-retention-cleanup/plan.md) | Local Data Retention & Cleanup | Completed | 查看本地证据占用并通过范围绑定授权清理过期 Artifact |
| [ITER-0049](./0049-desktop-workbench-foundation/plan.md) | Desktop Workbench Foundation | Completed | 桌面应用自动拉起并认证本地 Runtime，首页展示就绪诊断与设备列表 |
| [ITER-0050](./0050-desktop-task-workbench/plan.md) | Desktop Task Workbench | Completed | 桌面端提交自然语言 Agent 任务、展示执行时间线并查看完整报告 |
| [ITER-0051](./0051-agent-execution-resilience/plan.md) | Agent Execution Resilience | Completed | 观察瞬时故障有界重试、轮次预算数据校准与真机成功率基线 |
| [ITER-0052](./0052-desktop-device-screen/plan.md) | Desktop Device Screen & Live Observation | Completed | 桌面工作台设备画面栏：执行中与报告内查看真实轮次截图 |
| [ITER-0053](./0053-manual-takeover/plan.md) | Manual Takeover (Pause & Resume) | Completed | 执行中安全边界暂停 Agent、人工接管设备后恢复续跑，事件流记录接管区间 |
| [ITER-0054](./0054-desktop-settings/plan.md) | Desktop Settings & Model Provider Onboarding | Completed | 桌面设置页：模型 Provider 与 API Key 开箱配置（Keychain 注入），保存并重启生效 |
| [ITER-0055](./0055-desktop-ui-redesign/plan.md) | Desktop UI Visual Redesign | Completed | 桌面工作台整体视觉重设计：设计 tokens、卡片海拔、手机框设备画面、统一控件语言 |
| [ITER-0056](./0056-desktop-mono-theme/plan.md) | Desktop Mono Brand Theme | Completed | 桌面 mono 编辑风品牌主题：奶油纸底、墨框硬阴影、印章徽章与按压按钮（方向稿 3c 落地） |
| [ITER-0057](./0057-distribution-pipeline/plan.md) | Distribution Pipeline | Completed | macOS 分发流水线：Developer ID 签名（hardened runtime + 最小 entitlements）、公证脚本、tag 触发的 Release 自动发布与操作手册 |

迭代粒度、节奏、门禁和交付要求见[迭代开发规范](../engineering/iteration-process.md)；目录和文档
格式见[文档规范](../documentation-guide.md)。
