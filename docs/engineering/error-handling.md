# 错误与诊断规范

> 状态：Active
> 更新日期：2026-07-08

## 1. 目标

错误必须同时服务于用户理解、程序处理和开发诊断，不能把底层异常文本直接跨层传播。

## 2. Error Contract

```json
{
  "code": "DEVICE_OFFLINE",
  "category": "device",
  "message": "设备已断开连接",
  "retryable": true,
  "outcome": "known_failure",
  "suggested_action": "重新连接设备后重试",
  "correlation_id": "corr_...",
  "details": {},
  "artifact_refs": []
}
```

- `code`：稳定、可编程处理。
- `category`：`validation | device | capability | policy | execution | model | storage | internal`。
- `message`：可展示给用户，不包含敏感数据。
- `retryable`：仅表示在满足条件后可能重试，不授权自动重试。
- `outcome`：`known_failure | unknown_outcome | rejected`。
- `suggested_action`：下一步建议。
- `correlation_id`：关联本地日志。
- `details`：受控结构化诊断，不放任意 traceback。
- `artifact_refs`：相关证据引用。

## 3. 错误码

- 使用大写蛇形命名。
- 一个错误码只表达一种稳定语义。
- 不把包名、平台或 HTTP 状态嵌入错误码。
- 新增错误码必须登记并添加映射测试。
- 删除或改变错误语义属于 Contract 破坏性变化。

V1 基础错误：

```text
INVALID_ARGUMENT
DEVICE_NOT_FOUND
DEVICE_OFFLINE
DEVICE_UNAUTHORIZED
DEVICE_LOCKED
CAPABILITY_UNAVAILABLE
TOOL_REQUIRES_SKILL
TARGET_NOT_FOUND
TARGET_AMBIGUOUS
TARGET_NOT_CLICKABLE
TARGET_NOT_EDITABLE
TARGET_NOT_INTERACTABLE
TARGET_OUT_OF_BOUNDS
ACTION_REJECTED_BY_POLICY
CONFIRMATION_REQUIRED
ACTION_TIMEOUT
ACTION_OUTCOME_UNKNOWN
OBSERVATION_FAILED
LOG_CAPTURE_EMPTY
LOG_CAPTURE_FAILED
PERFORMANCE_SNAPSHOT_FAILED
APK_INVALID
APK_PACKAGE_MISMATCH
APP_ALREADY_INSTALLED
APP_NOT_FOUND
APPROVAL_INVALID
APK_INSTALL_FAILED
APK_INSTALL_NOT_VERIFIED
APP_STOP_FAILED
APP_STOP_NOT_VERIFIED
APP_DATA_CLEAR_FAILED
APP_DATA_CLEAR_NOT_VERIFIED
APP_STATE_INSPECTION_FAILED
MODEL_UNAVAILABLE
MODEL_OUTPUT_INVALID
NO_PROGRESS
TASK_CANCELLED
TASK_DEADLINE_EXCEEDED
TASK_INTERRUPTED
TASK_STATE_CONFLICT
IDEMPOTENCY_CONFLICT
TASK_NOT_FOUND
STORAGE_ERROR
RUNTIME_UNAVAILABLE
RUNTIME_RESPONSE_TOO_LARGE
MCP_RATE_LIMITED
INTERNAL_ERROR
```

`RUNTIME_UNAVAILABLE`、`RUNTIME_RESPONSE_TOO_LARGE` 与 `MCP_RATE_LIMITED` 属于本地 MCP Interface
诊断错误，不替代 Runtime 返回的领域错误。MCP 必须优先透传安全 Error Contract；只有连接失败、
响应无法解析、响应越界或 Interface 限流时才生成这些错误，且不得内联原始 HTTP body 或 token。

## 4. 异常映射

```text
Platform/Library Exception
→ Adapter or Infrastructure Error
→ Domain Error
→ REST / WebSocket / MCP Representation
```

- 原始 cause 保留在本地异常链和受控日志。
- 用户消息不显示 traceback、命令行、令牌或完整本机路径。
- 未知异常映射为 `INTERNAL_ERROR`，同时生成 correlation ID。
- 不使用 `except Exception: pass`。

## 5. HTTP 映射

- `400`：输入格式或语义错误。
- `401/403`：认证或策略拒绝。
- `404`：资源或设备不存在。
- `409`：状态冲突、设备锁或重复请求冲突。
- `422`：Contract 可解析但无法执行。
- `429`：限流或预算耗尽。
- `500`：未分类内部错误。
- `503`：设备、模型或依赖暂不可用。

HTTP 状态不替代领域错误码。

## 6. WebSocket 与 MCP

- WebSocket Error Event 使用同一 Error Contract，并携带 task sequence。
- MCP 返回简洁用户消息，同时在 structured content 中保留 code 和 retryable。
- 不把 MCP 协议错误用于表达普通设备业务失败。
- 不同接口对同一失败必须使用相同领域错误码。

## 7. 重试语义

`retryable=true` 需要调用方同时检查：

- 幂等属性
- outcome 不是 unknown
- 当前设备 Session
- Retry-After 或 backoff
- Task 预算与取消状态

Policy 拒绝、输入错误和 unknown outcome 默认不可自动重试。

Agent 页面定位和 `finish` 验证中，若 Runtime 能确定错误发生在设备动作派发前，可将该轮记为
failed 并继续规划；不得将可能已产生副作用的错误按此方式恢复。`MODEL_UNAVAILABLE.details.failure_kind`
使用 `timeout | http_status | connection | invalid_json`。`failure_phase` 使用可观察的
`response_headers | response_body | response_decode | transport`，不得把 `response_headers` 进一步
推断成 DNS、TCP、TLS 或首 Token 阶段。诊断只保留 HTTP status、配置 timeout、单次/总耗时、尝试和
重试次数等脱敏元数据。
`MODEL_OUTPUT_INVALID` 的 Selector 诊断只允许记录字段名、未知键、参数键和修复次数，不记录
Selector 值、模型响应体或密钥。模型输出省略非安全关键的 `reason` 时不产生错误，由 Runtime
写入固定审计说明；非字符串或超长 `reason` 仍使用 `MODEL_OUTPUT_INVALID`。

调用方提供 `AgentGoalAcceptance` 时，Runtime 对成功条件的只读验证失败继续使用
`TARGET_NOT_FOUND` 或 `TARGET_AMBIGUOUS`，并以 `verification_source=runtime_acceptance`
标识来源。该失败可作为 failed round 反馈 Planner，但不能被模型自述覆盖；请求结构无效则在
调用模型或设备动作前返回 `INVALID_ARGUMENT`。

`source=llm` 的 GoalSpec 未确认时返回 `CONFIRMATION_REQUIRED`，且必须发生在 Observation、模型
Planner 和设备动作之前。Compiler 输出结构无效使用 `MODEL_OUTPUT_INVALID`，诊断只记录字段名
和形状，不记录完整目标、模型响应、成功条件值或密钥。

异步排队取消使用 `TASK_CANCELLED`，表示后续工作已停止，不表示撤销已经完成的设备动作。
Runtime 重启时，未开始的排队任务以 `TASK_INTERRUPTED/known_failure` 结束；已经运行或取消中的
任务使用 `TASK_INTERRUPTED/unknown_outcome`，禁止自动重放。相同 `Idempotency-Key` 用于不同
请求时返回 `IDEMPOTENCY_CONFLICT` 和 HTTP 409；终态任务重复取消是幂等读取，不返回冲突。

设备写租约冲突使用 `DEVICE_LOCKED` 和 HTTP 409，details 只允许 owner_id 与 lease_expired 等
非敏感协调信息。任务总预算耗尽使用 `TASK_DEADLINE_EXCEEDED`，TaskRun/TaskExecution 状态为
`timed_out`；它不表示已经完成的设备动作被撤销。

任务绑定的设备断连或以同一 device_id 重连后使用 `DEVICE_SESSION_CHANGED`，旧任务不得自动在
新 Session 继续执行。共享同一数据目录启动第二个 Runtime 使用 `RUNTIME_ALREADY_RUNNING`，
启动过程不得覆盖现有 token 或创建第二个服务实例。

`RuntimeReadiness` 将已知错误映射为只读诊断 Issue。`blocked` 是可展示的就绪状态，不等同 HTTP
错误；因此 `/v1/readiness` 在 ADB 缺失、无设备或未授权时仍返回 HTTP 200。具体原因继续使用
`ADB_NOT_FOUND`、`DEVICE_NOT_FOUND`、`DEVICE_OFFLINE`、`DEVICE_UNAUTHORIZED` 或
`DEVICE_LOCKED`，客户端不得通过解析 message 推断状态。

APK 安装 Prepare 使用 `APK_INVALID`、`APK_PACKAGE_MISMATCH`、`APP_ALREADY_INSTALLED`；它们必须
发生在设备写动作前。短期 Approval 缺失、过期、被其他请求使用或确认后文件变化使用
`APPROVAL_INVALID`。ADB 明确拒绝安装使用 `APK_INSTALL_FAILED`；命令成功但 package manager
后置查询失败使用 `APK_INSTALL_NOT_VERIFIED`。安装等待超时使用 `ACTION_OUTCOME_UNKNOWN`，禁止自动重试。

应用卸载 Prepare 对系统应用或系统属性未知的应用使用 `SYSTEM_APP_PROTECTED`；Approval 缺失、
过期、被其他请求使用或确认后版本变化使用 `APPROVAL_INVALID`。ADB 明确拒绝卸载使用
`APP_UNINSTALL_FAILED`，命令完成但包仍存在使用 `APP_UNINSTALL_NOT_VERIFIED`。卸载等待超时使用
`ACTION_OUTCOME_UNKNOWN`，必须先只读检查安装状态，禁止自动重试。

## 8. 日志与诊断

- Error 日志包含 code、category、correlation、task/step/device ID。
- 相同错误不在每一层重复记录为 error；由负责处理或边界层记录一次。
- stdout/stderr 先限制、解析和脱敏，再作为 debug details。
- 高频可预期错误使用 warning/info，避免噪音淹没真实异常。
- Debug Bundle 可以包含结构化日志和证据，但必须经过用户授权与脱敏。

## 9. 用户体验

错误展示回答三个问题：

1. 发生了什么？
2. 任务或设备现在处于什么状态？
3. 用户下一步可以做什么？

禁止只显示“Something went wrong”或完整底层错误。

## 10. 测试

- 每个公开错误码有序列化测试。
- Adapter 常见 stderr 有确定映射。
- REST、WebSocket、MCP 保持相同 code。
- 敏感输入不会进入 message、details 和日志快照。
- unknown outcome 不被映射为普通 timeout 或 failed。
