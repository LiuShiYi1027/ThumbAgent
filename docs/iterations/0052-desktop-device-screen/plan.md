# ITER-0052 Desktop Device Screen & Live Observation

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-19

## 产品结果

桌面工作台落地产品方案三栏布局中的"设备画面"栏：Agent 任务执行中，每轮动作完成后面板
实时展示该轮动作后的真实设备截图；任务结束后的报告页可按轮次回看动作前后截图。用户
第一次能够在桌面端"看到"Agent 在设备上做了什么，而不只是读文字时间线。

## 背景

ITER-0050 交付了任务提交、执行时间线和报告，但桌面端没有任何设备视觉反馈；
solution-v1 §2.2/§7.2 把"实时设备画面"列为桌面工作台核心职责。当前阻碍是：
Runtime 的证据 Artifact 只落盘，REST 不提供内容读取（ITER-0036 起"公共结果不内联正文"），
桌面 IPC 也只有 JSON 通道。

## 范围

- Runtime 新增只读端点 `GET /v1/artifacts/{artifact_id}/content`：
  - 仅服务 screenshot 类 Artifact（`.png`），按 `artifact_id` 模式校验后在 Artifact
    根目录内定位系统生成文件，重新验证 PNG 签名，单文件上限 8 MiB；
  - 与所有 GET 不同，该端点要求 Bearer token 认证（证据内容比元数据敏感）；
  - 响应 `image/png` + `Cache-Control: no-store` + `X-Content-Type-Options: nosniff`；
  - 不开放任意路径、其他 Artifact 类型或目录列举。
- `task.step_completed` 事件 payload 增加可选 `screenshot_artifact_id`（该轮
  action_result / skill_result 的 after Observation 截图），payload 为开放 object，
  属兼容性新增。
- 桌面 IPC 增加 `runtime_api_get_bytes`：路径白名单只允许上述 Artifact 内容模式，
  响应大小有界，base64 编码返回前端（不新增 Rust 依赖）。
- 桌面 UI 增加 `DeviceScreenPanel`：执行中轮询事件流并展示最新轮次截图；报告视图
  支持按轮次查看动作后截图；无截图时展示明确占位说明。
- App 布局：任务进行中/结束后采用"设备画面 + 执行工作区"双栏，空闲时保持现有首页。

## 非目标

- 不做连续视频流、实时远程控制或人工接管（人工接管是后续独立迭代）。
- 不改变其他 GET 端点的认证现状，不重构首页设备列表。
- 不通过该端点暴露 UI Tree、日志、诊断包等文本/归档内容。
- 不修改任务、Observation 的既有 JSON Contract 字段；不引入 WebSocket。
- 不新增 Rust crate 或前端依赖。

## 依赖

- 既有 ArtifactStore 系统生成命名（`artifact_<hex>.png`）与日期目录布局（ITER-0002）。
- 既有 TaskEvent 开放 payload（ITER-0031）与 TaskRun 中 action_result 的
  before/after Observation 截图引用（ITER-0023）。
- 桌面 sidecar IPC 白名单模式（ITER-0049/0050）。

## 风险与兼容性

- 新增端点 + 事件 payload 可选字段均为兼容性新增，无破坏性变更；生成类型无需变化。
- 证据内容首次经 REST 提供读取：信任边界不变（loopback + Bearer token），仅截图、
  只读、有界；不扩展为通用文件读取。该决策记录于此，不单独建 ADR（未修改信任模型
  或风险策略分级）。
- 截图含屏幕敏感内容：端点 `no-store`，桌面端只在内存中渲染，不复制到磁盘。
- 执行中轮询截图的频率受事件轮询（1.2s）约束，单次 PNG 通常 < 2 MiB，本地开销可控。

## 预算

- 5 个 Task，目标 2 个工作日。
- 开发阶段只运行 focused tests；候选稳定后运行一次完整 `make check` + `make check-desktop`。
- 真机验证为 Low 风险只读场景：跑一条 Agent 任务后用新端点取回截图验证。
