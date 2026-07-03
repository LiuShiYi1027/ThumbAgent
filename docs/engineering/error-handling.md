# 错误与诊断规范

> 状态：Active  
> 更新日期：2026-07-03

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
STORAGE_ERROR
INTERNAL_ERROR
```

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
