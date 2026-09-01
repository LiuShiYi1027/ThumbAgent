# ADR-0020: 系统权限弹窗前台的点击动作拒绝派发

- Status: Accepted
- Date: 2026-09-01
- Deciders: Mobile Agent Team

## Context

ITER-0061 真机验收（2026-09-01，MagicOS BKQ-AN10）实测：Agent 在夸克浏览器的
录音权限弹窗上自主点击「仅使用期间允许」（`input.tap_element` 命中
`permission_allow_foreground_only_button`），动作成功执行。

产品文档与 `security.md` §6 将「修改账号、权限和安全设置」定义为 High 风险、
必须明确确认；但点击权限弹窗按钮走的是通用点击能力 `input.tap@1`
（Medium，任务级 confirmed 即放行）。风险定级按动作类型静态赋予，无法表达
「同一个 tap，落在权限弹窗上等于权限授予」这一上下文语义。这是模型可借道
低/中风险通用动作完成 High 风险效果的真实逃逸路径。

## Decision

在 Tool 执行管线的动作派发前（前置 Observation 已采集、`_dispatch` 之前）
增加上下文守卫：当 `before.foreground_app.app_id` 属于系统权限弹窗包
（`com.android.permissioncontroller`、`com.google.android.permissioncontroller`）
时，`input.tap` 与 `input.tap_element` 一律以 `ACTION_REJECTED_BY_POLICY`
拒绝，不携带确认豁免。

权限决策由用户通过既有「暂停 + 人工接管」链路完成（ITER-0053），接管区间
正常计入事件流；Agent 恢复后看到的是用户决策后的页面状态。

拒绝发生在任何设备写动作之前；守卫不依赖模型提供的任何字段，只依赖 Runtime
自己采集的前台包名。

## Consequences

- Agent 遇到权限弹窗会得到明确策略拒绝并停止，引导用户接管——符合
  「无法确认时主动停止并请求用户介入」的产品原则。
- 每个被守卫动作本来就需要前置 Observation，守卫复用该观察，零额外设备调用。
- 守卫在 Tool 执行层生效，对 Agent 循环、REST 直调、MCP 调用一致适用，
  不存在绕过路径（不经过 ToolRuntime 的设备写入不存在）。
- 未守卫 swipe/text/back：滑动与文本输入无法激活弹窗按钮；Back 解散弹窗
  的语义是拒绝授权，方向保守。

## Alternatives Considered

- **风险动态升级为 High + 确认**：需要把「当前前台」传入 Policy Engine 并引入
  权限弹窗专属确认面；但权限授予的效果不可逆且与用户意图强绑定，即使是
  confirmed 的任务也不应默许模型代决策。拒绝 + 人工接管更简单也更安全。
- **在 Agent Runner 层拦截**：只覆盖 Agent 路径，REST/MCP 直调工具时失效；
  且 Runner 拦截依赖上一轮观察，弹窗可能在其后弹出。Tool 执行层的前置
  Observation 是最接近动作时刻的检查点。
- **包名覆盖更广的系统弹窗（如 packageinstaller 安装确认）**：本期只处理
  实测暴露的权限弹窗向量；安装确认等弹窗若未来暴露真实需求再扩展集合，
  不提前抽象。

## Follow-up

- 真机回归：在权限弹窗场景确认 Agent 收到拒绝、人工接管链路可用。
- 观察 ROM 差异：若厂商 ROM 使用非标准权限弹窗包名，按实测补充集合。
