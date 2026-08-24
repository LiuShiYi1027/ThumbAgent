# ITER-0059 Unicode Text Input Helper

> 文档状态：Active
> 迭代状态：Planned
> 创建日期：2026-08-24
> 关联：[能力路线图](../../product/capability-roadmap.md)（A 档首选） · [技术设计 §11.4](../../architecture/technical-design-v1.md) · [ADR-0018](../../adr/0018-programmatic-navigation-shortcuts.md)

## 背景

当前 `input.text` 只允许 `[A-Za-z0-9._-]{1,64}`：不支持中文、空格、常见标点。
这使「搜索中文关键词」「填写中文表单」「发送中文消息」等高频任务完全不可用——
CJK 输入是 A 档候选中唯一的硬阻塞项（能力路线图 §4.1）。

Android 平台侧没有免安装的 Unicode 注入通道：`input text` 对非 ASCII 支持不一致，
`cmd clipboard` 在 Android 10+ 受后台限制。行业通行做法是受控输入法 helper：
安装一个最小广播接收 IME，Runtime 切 IME → 广播文本 → 读回验证 → 恢复原 IME。

## 目标

- 新增 `input.unicode@1` Capability：经受控 IME helper 输入 Unicode 文本
  （CJK、空格、常见标点），长度有界，沿用现有敏感输入拦截（验证码/手机号等
  数字形态一律拒绝，helper 不得成为绕过通道）。
- IME 切换是设备状态变更：执行前记录当前默认 IME，完成后必须恢复；
  恢复失败必须显式报错，不得静默遗留 helper 为默认输入法。
- 输入后通过 UI Tree 读回目标输入框内容做后置验证，不一致返回专用错误码，
  不自动重试。
- helper APK 的安装复用既有 `app.install@1` 两阶段 High 风险授权链路，
  不在本迭代新开安装通道。
- 提供确定性 Skill、REST 与 MCP 入口；进入 Agent allowlist，使中文目标
  可以经由模型循环或捷径完成输入步骤。

## 非目标

- 不做剪贴板通道（B 档，治理设计独立迭代）。
- 不支持密码框/验证码框输入；不放宽现有数字形态拦截。
- 不内置第三方二进制 APK 进仓库而不经信任评审（见关键决策）。
- 不修改 ASCII 快路径：纯 ASCII 文本仍走现有 `input text`，不触发 IME 切换。

## 关键决策（TASK-0059-01 产出 ADR-0019）

- **helper 分发信任模型**：
  - 方案一：vendor 开源 ADBKeyBoard（Apache-2.0），需 license 与二进制完整性评审；
  - 方案二：自构建最小广播 IME（源码入仓、CI 构建、SHA-256 固定），信任链最短
    但引入 Android 构建工具链；
  - 方案三：首次使用时由用户经 `app.install` 流程显式安装自带 APK，Runtime
    不分发二进制。
- **IME 切换授权语义**：单次任务内切换 + 自动恢复，还是范围绑定 Approval。
- **读回验证的容差**：IME 候选词/自动纠正可能改变文本，验证策略需明确
  （精确比对还是前缀/归一化比对）。

## 兼容性

新增 Contract Schema、Capability、Tool、Skill、REST 端点与 MCP Tool，均为向后兼容
变化；无数据库迁移。现有 `input.text@1` 语义不变。

## 风险与应对

- **helper 成为任意文本注入口**：广播 action 与 extras key 固定，Adapter 只接受
  纯文本参数；敏感数字形态在 Tool 层拦截，先于任何设备动作。
- **IME 恢复失败遗留**：恢复步骤独立错误码 + 任务报告显著标记；E2E 覆盖恢复路径。
- **厂商 ROM 的 IME 管理差异**（MagicOS 等可能拦截 `ime set` 或弹确认框）：
  真机 E2E 在 MagicOS 上验证；失败时返回 `CAPABILITY_UNAVAILABLE` 并降级提示
  人工输入（技术设计 §11.4 既有语义）。
- **二进制供应链**：无论选哪个分发方案，helper APK 的 SHA-256 固定登记，
  安装前校验摘要不符即拒绝。

## 新错误码（实施时登记到 error-handling.md）

```text
IME_HELPER_NOT_INSTALLED     # helper 未安装或未启用（提示经 app.install 流程安装）
IME_SWITCH_FAILED            # ime set 失败或被 ROM 拦截
TEXT_INPUT_NOT_VERIFIED      # 读回内容与目标文本不一致
IME_RESTORE_FAILED           # 原 IME 恢复失败（必须显著上报）
```

## 测试与验收要点

- Tool 层：Unicode 文本接受、ASCII 走快路径、敏感数字形态拒绝、长度上限。
- Adapter 层：固定 argv 快照（ime/broadcast 参数数组）、恢复路径、ROM 拦截映射。
- Skill 测试矩阵按 skill-development.md §10 全覆盖。
- 真机 E2E：MagicOS 设备中文输入读回一致、IME 恢复验证、helper 未安装时的
  降级提示路径。
