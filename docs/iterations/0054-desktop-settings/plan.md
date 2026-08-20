# ITER-0054 Desktop Settings & Model Provider Onboarding

> 文档状态：Done
> 迭代状态：Done
> 更新日期：2026-08-20

## 产品结果

桌面工作台新增设置页：用户无需手工编辑 `model-provider.json` 或环境变量，即可查看模型
Provider 状态、填写 base_url/model/超时、输入模型 API Key，一键「保存并重启 Runtime」后
Agent 任务即使用真实模型。API Key 只进入 macOS Keychain 与 Runtime 进程环境，不写入
配置文件、数据库或日志。数据目录与配置文件路径在设置页可见并可在 Finder 中打开。

## 背景

ITER-0049–0053 让桌面端成为主要交互面，但模型配置仍停留在开发者路径：用户要手工写
`<data-dir>/model-provider.json`，并自行解决 `env:MOBILE_AGENT_MODEL_SECRET_*` 的密钥
注入——而桌面 sidecar 启动 Runtime 时并不注入任何模型密钥，导致桌面路径下真实模型
事实上不可用（`MODEL_UNAVAILABLE`）。本迭代把「模型开箱配置」这一最后的手工环节搬进
桌面 UI，闭环密钥链路：UI 输入 → Keychain → sidecar 注入 env → Runtime `env:` 引用解析。

## 范围

### In Scope

1. Runtime 配置面：`GET /v1/model-provider/config`（返回非敏感字段、配置文件路径与
   env 覆盖标记）与 `POST /v1/model-provider/config`（校验后原子写入
   `<data-dir>/model-provider.json`，0600，密钥引用只允许
   `env:MOBILE_AGENT_MODEL_SECRET_*` 模式，密钥值永不经过该端点）。
2. 桌面 sidecar：macOS Keychain 读写删（`/usr/bin/security` 固定参数数组，无新增 crate）、
   启动 Runtime 时注入 `MOBILE_AGENT_MODEL_SECRET_DESKTOP`、`restart_runtime` 命令
   （换 token 重启子进程）、`reveal_in_finder`（`open -R` 固定命令）。
3. 设置页 UI：模型 Provider 状态与表单、密钥保存/清除、保存并重启（含任务中断提醒）、
   数据目录展示与 Finder 打开。
4. 规范同步：technical-design-v1.md、README、迭代文档。

### Out of Scope

- Runtime token 管理（桌面路径下 token 是 sidecar 每次启动生成的会话值，无需管理）
- 数据目录迁移/修改（只读展示）
- Linux/Windows Keychain（桌面 V1 仅 macOS；命令按 macOS 实现并在其他平台返回明确错误）
- 模型连通性测试按钮（保存后跑一次真实任务即验证，本迭代不做 ping 端点）
- 多 Provider 配置档案

## 设计决策

1. **密钥不经过 Runtime 配置端点**。`POST /v1/model-provider/config` 只接收
   `api_key_ref`（且强制 `env:MOBILE_AGENT_MODEL_SECRET_*` 模式）；密钥值由桌面 UI
   直接写入 Keychain，sidecar 启动时注入 env。Runtime 磁盘上永远只有引用没有值
   （安全规范：密钥不写入代码、数据库、日志）。
2. **桌面路径固定引用名** `env:MOBILE_AGENT_MODEL_SECRET_DESKTOP`。sidecar 独占该
   Keychain 项（service `thumbagent.desktop.model-secret`），与 MCP 预览脚本的
   既有条目互不干扰；非桌面启动（make run）仍按原方式自行注入 env。
3. **配置生效 = 重启 Runtime**。模型设置在启动时加载（ITER-0019），保存后必须重启；
   sidecar `restart_runtime` 换新会话 token 重启子进程，UI 明确提示「重启会中断
   正在运行的任务」并需确认。Runtime 重启后非终态任务按既有 `TASK_INTERRUPTED` 收尾。
4. **env 覆盖优先的既有语义不变**。`GET` 响应带 `env_override: true` 时说明
   `MOBILE_AGENT_MODEL_*` 环境变量在生效，文件修改不会改变运行时行为——避免用户
   在设置页改了却不生效的困惑。
5. **GET 配置不需要 token**（与 `GET /v1/model-provider/status` 一致，loopback 且
   无敏感值）；POST 沿用 `_authorize_post` Bearer 认证。
6. **写入原子性**：临时文件 + `os.replace` + 0600；写坏不破坏旧配置。
7. **不新增 ADR**：密钥信任边界不变（仍 `env:` 引用 + 进程环境注入），无依赖方向、
   分层或风险策略变化；sidecar 仅调用 macOS 固定命令，符合安全规范的进程规则。
8. **Keychain/重启逻辑只做纯函数级单测**（argv 构造、状态迁移），不在 CI 执行真实
   Keychain 或进程操作；真实链路验证在真机环节由本机完成。

## 兼容性与风险

- `POST /v1/model-provider/config` 是新的本地写面：仅 loopback + token，写固定路径
  （数据目录内），不接受任意路径；字段复用 ITER-0017/0019 的校验。
- 重启中断任务的 UX 风险：用确认对话框 + 中断后任务按 `TASK_INTERRUPTED` 可见收尾。
- 主要实现风险：sidecar 重启时健康检查循环的状态竞争。缓解：重启复用 spawn 路径，
  状态迁移集中在 Mutex 内；补 Rust 单测。

## 验证策略

- Runtime：GET（默认值/文件存在/env_override）、POST（校验错误、禁用保存、原子写、
  0600、密钥值不落盘断言）、API 401。
- Rust：argv 构造、密钥状态解析、restart 状态机。
- 前端：oxlint + tsc。
- 门禁：完整 `make check` 与 `make check-desktop`。
- 真机 Low 风险：经新端点写入真实硅基流动配置（base_url/model/固定引用名）→
  模拟 sidecar 注入 env 重启 Runtime → GET 确认生效 → 跑
  `settings.display-brightness.v1` 证明真实模型链路经新配置面可用
  （提交时 confirmed=true 即人工确认，本 plan 预授权该场景）。
