# Mobile Agent Agent Guide

本文件适用于整个仓库。子目录存在更具体的 `AGENTS.md` 时，子目录规则在其作用域内优先。

## 1. 开始工作前

必须依次阅读：

1. `README.md`
2. `docs/product/positioning.md`
3. `docs/product/solution-v1.md`
4. `docs/architecture/technical-design-v1.md`
5. `docs/engineering/development.md`
6. `docs/iterations/README.md`
7. 与任务相关的迭代文档、目录级 `AGENTS.md` 和 ADR

修改 Contract、Skill、持久化、执行语义或错误体系时，还必须阅读对应专项规范：

- `docs/engineering/contract-versioning.md`
- `docs/architecture/capability-model.md`
- `docs/engineering/skill-development.md`
- `docs/architecture/reliability-model.md`
- `docs/engineering/data-migrations.md`
- `docs/engineering/error-handling.md`

开始修改前必须检查工作区状态。已有修改可能属于用户或其他 Agent，不得覆盖、回滚或顺手重构。

## 2. V1 边界

V1 目标是完成单台 Android 设备的本地 AI-to-Device 闭环：设备发现、Observation、基础动作、Skills、任务状态、安全策略、证据和报告。

未经明确任务授权，不实现：

- iOS 或鸿蒙真实 Adapter
- 多设备并行调度
- 任意 Shell 执行
- 支付、验证码或权限绕过
- 云端账号、团队空间或遥测上传
- 与当前任务无关的未来能力

## 3. 强制架构边界

依赖只能沿以下方向：

```text
Clients / Interfaces
        ↓
Application / Skills / Task Engine
        ↓
Domain / Policy / Contracts
        ↓
Device Gateway
        ↓
Platform Adapters
```

- Desktop、CLI、MCP 不得直接执行 ADB 或修改任务存储。
- Skill 不得绕过 Tool Registry、Policy Engine 或 Device Gateway。
- Domain 不得依赖 FastAPI、Tauri、具体模型 SDK 或 Android 实现。
- Adapter 不得包含产品流程、Agent 决策或 UI 逻辑。
- MCP 是外部接口，不是内部模块总线。
- 模型输出一律视为不可信输入。

详见 `docs/architecture/rules.md`。

## 4. Contract-first

跨模块数据必须先在 `contracts/schemas/` 定义 Schema，再生成或实现语言类型。

以下对象禁止由 Python 与 TypeScript 各自手写一份近似定义：

- Device
- Observation
- Task
- ToolCall
- Skill Manifest
- Error
- Event

修改 Contract 时必须：

1. 说明兼容性影响。
2. 更新生成类型或消费者。
3. 添加 Contract 测试。
4. 必要时增加 ADR。

## 5. 安全规则

- 禁止 `shell=True`。
- 禁止拼接模型文本形成命令。
- 系统进程必须使用固定可执行文件和参数数组。
- 所有设备动作必须绑定明确的 `device_id`。
- 所有动作必须经过 Schema、Capability 和 Policy 校验。
- 密钥、令牌、密码、验证码不得写入代码、数据库、日志或测试快照。
- 高风险动作不得以“开发方便”为理由绕过确认。
- 不得实现隐藏的任意命令逃生口。

详见 `docs/engineering/security.md`。

## 6. 代码要求

- Python 新代码必须有类型标注；公共接口必须有简洁 docstring。
- TypeScript 禁止无理由使用 `any`。
- 领域错误使用统一错误码，不以裸字符串跨层传播。
- I/O、时间、随机数、模型和设备依赖必须可替换，便于测试。
- 不为假想需求提前抽象；出现第二个真实实现需求时再提炼通用层。
- 不混入与当前任务无关的格式化、重命名或重构。
- 注释解释原因和约束，不重复代码表面含义。

## 7. 测试要求

- Bug 修复必须先有能复现问题的测试或等价回归用例。
- 新 Tool/Skill 必须包含成功、参数错误、能力不足和策略拒绝测试。
- 普通单元测试不得依赖真实设备、网络或模型服务。
- Adapter 逻辑优先用 Fake Runner 或录制样本测试。
- 跨层功能至少提供一条集成测试。
- 真实设备 E2E 必须显式标记，不能进入默认快速测试集。

详见 `docs/engineering/testing.md`。

## 8. 多 Agent 协作

- 一个任务只修改完成目标所需的最小模块。
- 并行任务优先按模块拆分，避免共同修改核心注册表或 Contract。
- 发现冲突风险时先报告，不自行覆盖其他修改。
- 不使用 `git reset --hard`、`git checkout --` 等破坏性命令。
- 不删除不属于当前任务的未跟踪文件。
- 架构、协议、持久化或安全策略变化必须记录理由。

详见 `docs/engineering/agent-collaboration.md`。

## 9. Definition of Done

任务完成前必须确认：

- 实现符合任务和 V1 范围。
- 架构依赖方向没有被破坏。
- 相关测试、格式化和类型检查通过。
- 错误、取消、超时和边界条件得到处理。
- 没有泄露敏感信息。
- Contract、迁移、文档和 ADR 已按需更新。
- 没有覆盖或混入无关修改。
- 最终交付说明包含：变更、验证、已知限制。

如果受环境限制无法运行某项验证，必须明确说明未运行的命令和原因，不能宣称已经通过。

## 10. 架构决策

以下变化需要 ADR：

- 新增或替换核心框架、存储、协议或 Runtime
- 修改模块依赖方向
- 修改 Tool/Skill 分层
- 修改平台 Adapter 边界
- 修改安全信任模型或风险策略
- 破坏性 Contract/API 变更

ADR 模板与索引见 `docs/adr/README.md`。
