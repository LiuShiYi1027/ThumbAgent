# Contract 与 API 演进规范

> 状态：Active  
> 更新日期：2026-07-03

## 1. 适用范围

本规范适用于跨模块、跨进程或需要持久化的数据契约，包括：

- JSON Schema
- REST Request/Response
- WebSocket Event
- MCP Tool 输入输出
- Python/TypeScript 生成类型
- Device、Observation、Task、ToolCall、Skill Manifest、Error

进程内部私有类型不要求发布 Contract，但一旦被两个独立模块依赖，就必须迁入 `contracts/schemas/`。

## 2. 真源

- `contracts/schemas/` 是跨语言 Contract 唯一真源。
- `contracts/generated/` 是生成产物，禁止手工编辑。
- REST、WebSocket 和 MCP 可以有传输层包装，但领域字段语义必须一致。
- 示例数据必须通过对应 Schema 校验。

## 3. 版本模型

- 公共 API 使用路径主版本，例如 `/v1/tasks`。
- Schema 使用明确的 `$id` 和语义版本元数据。
- Skill 独立使用语义版本。
- Event 必须包含 `schema_version`。
- 仅文档澄清且不改变验证和语义时，不提升 Contract 版本。

## 4. 兼容性规则

### 向后兼容

- 新增可选字段，并提供安全默认行为。
- 新增枚举值，但消费者已明确实现 unknown fallback。
- 放宽输入约束且不会改变已有输入结果。
- 新增端点、Skill 或 Event 类型。

### 破坏性变化

- 删除字段、端点、事件或枚举值。
- 将可选字段改为必填。
- 改变字段类型、单位、默认值或语义。
- 收紧已发布输入约束。
- 改变相同请求的副作用、风险或幂等语义。
- 将同步结果改为异步任务而不改变 Contract。

破坏性变化必须提升主版本、提供迁移说明，并通过 ADR 批准。

## 5. 字段规则

- 已发布字段名不得复用为不同含义。
- 时间统一为 UTC ISO 8601，并以字段名或描述明确语义。
- 时长统一使用毫秒，字段后缀 `_ms`。
- 大小统一使用字节，字段后缀 `_bytes`。
- ID 是不透明字符串，消费者不得解析内部结构。
- 可空与缺失具有不同含义时必须在 Schema 中说明。
- Map 的 key 空间必须受约束，不能用于逃避类型设计。

## 6. 枚举演进

- 服务端新增枚举前，所有客户端必须有 unknown fallback。
- 状态机枚举不能仅靠 fallback；新增状态必须同步更新消费者、测试和文档。
- Error Code 可以向后兼容新增，但客户端必须依据分类字段而非字符串猜测处理方式。

## 7. 废弃流程

1. 标记 `deprecated`，说明替代字段或接口。
2. 发布迁移示例和最短保留周期。
3. 在日志或开发工具中提示使用方，不向最终用户制造噪音。
4. 仅在下一主版本删除。

V1 Preview 阶段最短保留一个小版本；进入 Stable 后最短保留两个小版本，除非存在安全风险。

## 8. Contract 变更流程

1. 修改 Schema 真源。
2. 判断兼容性并记录结论。
3. 重新生成各语言类型。
4. 更新生产者和消费者。
5. 添加正向、反向和无效样本测试。
6. 运行生成文件一致性检查。
7. 破坏性变化新增 ADR 和迁移指南。

## 9. API 要求

- 创建异步任务返回 `202 Accepted` 和稳定 `task_id`。
- 变更请求支持 `Idempotency-Key`。
- 分页使用 opaque cursor，不暴露数据库 offset 作为长期 Contract。
- Error Response 使用统一 Error Contract。
- WebSocket 事件包含 `event_id`、`occurred_at`、`schema_version`、关联 ID 和序列号。
- 客户端可通过 REST 重建状态，不依赖完整事件历史。

## 10. MCP 映射

- MCP 默认暴露目标级 Skill，不暴露全部原子 Tool。
- MCP Tool 名称稳定，内部 Skill ID 变化不能静默改变外部语义。
- MCP 错误映射保留领域 `code`、`retryable` 和建议动作。
- MCP 不能提供 REST 不允许的权限或绕过确认机制。

## 11. 评审清单

- 这是新增、兼容变化还是破坏性变化？
- Python、TypeScript、REST、Event、MCP 是否同步？
- 单位、空值、默认值和枚举 fallback 是否明确？
- 是否需要数据库迁移？
- 是否改变风险、幂等或副作用？
- 是否提供 Contract 测试和迁移说明？
