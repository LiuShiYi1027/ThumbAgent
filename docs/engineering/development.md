# 工程开发规范

> 状态：Active  
> 更新日期：2026-07-03

## 1. 目标

本规范将技术方案转化为日常开发约束，使多个开发者和 Agent 能够独立交付、稳定集成。

## 2. Monorepo 约定

计划目录职责：

```text
apps/desktop/          桌面 UI 与 Tauri 容器
runtime/               Python Runtime
interfaces/mcp/        MCP 接口适配
interfaces/cli/        CLI 接口适配
contracts/schemas/     跨语言 Schema 真源
contracts/generated/   自动生成类型，不手工编辑
docs/                  工程规范与 ADR
```

模块内部实现不得反向依赖客户端。生成目录必须标记生成方式，并在 CI 检查是否与 Schema 一致。

## 3. Python 规范

- 目标版本：Python 3.11+。ITER-0001 使用本机可用的 3.11 建立零外部依赖骨架；引入框架依赖时通过锁文件固定版本。
- 包管理和构建配置统一放在 `pyproject.toml`。
- 格式化与静态检查建议使用 Ruff。
- 类型检查建议使用 Pyright。
- 测试使用 pytest 与 pytest-asyncio。
- 使用 `pathlib.Path` 处理路径。
- 异步 I/O 使用 `asyncio`，不得在事件循环中执行阻塞设备命令。
- Pydantic 模型用于外部边界；领域内部避免把所有对象都做成 API DTO。
- Repository、Clock、ID Generator、Model Provider 和 Device Adapter 必须可注入。

## 4. TypeScript 规范

- 启用严格类型检查。
- API 类型从 Contract 生成。
- 服务端状态通过统一 Query 层管理，避免组件各自请求和缓存。
- 任务状态以服务端为真源，前端不得猜测或私自推进状态。
- 前端不得读取模型密钥或直接启动系统命令。
- UI 错误展示使用错误码映射，不解析后端错误字符串。

## 5. 命名约定

- Tool ID：`domain.verb`，例如 `screen.observe`、`app.launch`。
- Skill ID：目标级语义，例如 `app.open`、`task.execute_mobile`。
- Capability：与 Tool 语义一致且稳定，例如 `input.tap`。
- API：复数资源名与版本前缀，例如 `/v1/tasks/{task_id}`。
- Error code：大写蛇形，例如 `DEVICE_OFFLINE`。
- Event name：过去式领域事件，例如 `task.status_changed`。

## 6. 配置

配置优先级：

```text
显式启动参数 > 环境变量 > 用户配置文件 > 安全默认值
```

- 配置模型必须校验。
- 密钥只保存到系统 Keychain，配置文件仅保存引用。
- 开发、测试和生产配置不得通过隐式全局状态切换。
- 所有危险能力默认关闭。

## 7. 时间、ID 与幂等

- 持久化时间统一使用 UTC ISO 8601。
- 展示层转换到用户时区。
- 领域 ID 使用带类型前缀的不可预测 ID，例如 `task_...`、`obs_...`。
- 变更 API 支持幂等键。
- 设备动作默认不自动重试；只有明确标记为安全且幂等的动作可以重试。

## 8. 错误处理

- 底层异常映射为领域错误，保留 cause 供本地调试。
- 用户消息说明发生了什么以及下一步怎么做。
- 不把 stdout/stderr 原样返回给模型或 UI。
- 取消不是失败；超时、取消、策略拒绝必须使用不同状态。
- 不捕获后静默忽略异常。

## 9. 日志

- 使用结构化日志，不拼接多行调试文本。
- 关联字段包含 `correlation_id`、`task_id`、`step_id` 和 `device_id`。
- 默认对文本输入、UI 文本和路径进行最小化记录。
- 日志不得改变业务流程或成为状态真源。

## 10. 依赖管理

- 新增依赖前确认标准库或现有依赖不能合理解决。
- 核心依赖需要说明用途、许可证、维护状态和替代方案。
- 禁止仅为一个简单工具函数引入大型框架。
- 锁文件必须提交并由同一工具更新。
- 升级依赖不得混入无关功能变更。

## 11. 文档同步

- 产品范围变化更新产品方案。
- 模块边界变化更新技术方案和 ADR。
- 用户可见行为变化更新 README 或用户文档。
- Contract 变化更新 Schema 与示例。
- 测试命令变化只在 `CONTRIBUTING.md` 维护权威入口。
