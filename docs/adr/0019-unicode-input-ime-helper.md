# ADR-0019: Unicode 文本输入的受控 IME Helper

- Status: Accepted
- Date: 2026-08-24（2026-08-24 经项目负责人确认方向）
- Deciders: Mobile Agent Team

## Context

`input text` 不支持 Unicode（CJK、空格、 Emoji），这是中文任务的硬阻塞
（能力路线图 A 档首选）。Android 没有免安装的 Unicode 注入通道，通行做法是受控
IME helper。调研确认了两条可行技术路线：

1. **广播 IME**（ADBKeyBoard）：`am broadcast -a ADB_INPUT_B64 --es msg <base64>`
   注入文本。问题明确：仓库无清晰许可证声明、官方分发的是 debug 签名 APK、
   维护停滞；且广播接收器在 helper 激活期间构成常开注入面——任何本地进程都能
   向焦点输入框注入文本和按键。
2. **UTF-7 编码 IME**（TOYAMA Sumio 实现，Appium `io.appium.android.ime` 沿用）：
   文本在主机侧编码为 Modified UTF-7（纯 ASCII），经既有 `input text` 管道送入，
   helper IME 解码上屏。无广播接收器，攻击面最小；Apache-2.0 许可，实现极小
   （单个 InputMethodService 解码器）。

两条路线共同的安全语义：helper 激活期间用户的正常键盘不可用，因此切换必须是
短时的、可恢复的。

## Decision

- **技术路线**：采用 UTF-7 编码 IME。不引入广播注入面；输入继续走既有
  固定 argv `input text` 管道，Adapter 无新命令面。
- **分发信任模型（方案二）**：以 Apache-2.0 的 TOYAMA/Appium 实现为参考，自构建
  最小 IME（源码入仓、一次性本地构建、APK 与 SHA-256 固定登记）。不分发任何
  第三方预编译二进制；安装一律走既有 `app.install@1` 两阶段 High 风险授权，
  安装前校验 SHA-256 摘要，不符即拒绝。
- **切换/恢复语义**：`input.unicode@1` 为 Medium 风险、需明确确认。每次调用在
  Session 与 Lease 内完成：记录当前默认 IME → `ime enable` + `ime set` helper →
  UTF-7 编码输入 → UI Tree 读回验证 → 恢复原 IME。恢复原 IME 是强制步骤，
  失败返回 `IME_RESTORE_FAILED` 并在任务报告中显著标记，不得静默遗留。
- **验证容差**：读回内容与目标文本 NFC 归一化后精确比对；IME 自动纠正导致的
  不一致返回 `TEXT_INPUT_NOT_VERIFIED`，不自动重试。
- **敏感输入拦截不变**：验证码（4–8 位数字）、手机号（11+ 位）等形态在 Tool 层
  先于任何设备动作拒绝；helper 不得成为绕过通道。纯 ASCII 文本仍走现有快路径，
  不触发 IME 切换。

## Consequences

- 需要一次性引入 Android 构建工具链（Android SDK + Gradle）构建 helper；
  构建是低频手动动作，不进入日常 `make check` 与 CI 门禁。
- 仓库新增 helper 源码目录与登记的二进制 + 摘要；后续 helper 变更必须重新评审
  并更新摘要。
- 用户首次使用 Unicode 输入前需完成一次 High 风险安装授权；之后每次输入只需
  Medium 风险确认。
- 厂商 ROM 可能拦截 `ime set`（MagicOS 已有先例）：映射 `IME_SWITCH_FAILED`，
  降级提示人工输入，保持 §11.4 既有语义。

## Alternatives Considered

- **vendor ADBKeyBoard 预编译 APK**：许可证不清晰、debug 签名、维护停滞、
  广播注入面，四项均不可接受，拒绝。
- **vendor Appium 预编译 UnicodeIME APK**：许可清晰（Apache-2.0）但分发渠道是
  npm 包内二进制，供应链不可审计；作为自构建失败的备选保留。
- **用户自带 APK 显式安装（方案三）**：零分发负担但开箱体验差、版本不可控；
  作为高级用户的逃生路径，由 `IME_HELPER_NOT_INSTALLED` 错误信息引导，不作为
  默认分发方式。
- **剪贴板通道**：Android 10+ 后台限制且剪贴板是敏感数据源，属 B 档独立治理。

## Follow-up

- 真机 E2E 在 MagicOS 验证 `ime set` 是否被拦截、读回验证与恢复路径。
- 观察厂商 ROM 对 helper IME 的兼容反馈，评估是否需要在更多 ROM 采样。
- helper 源码仓库布局与构建脚本在 TASK-0059-02 落地。
