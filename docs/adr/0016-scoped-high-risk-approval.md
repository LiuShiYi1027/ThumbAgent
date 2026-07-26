# ADR-0016: High 风险动作使用两阶段、单次、范围绑定的授权

- Status: Accepted
- Date: 2026-07-22
- Deciders: Mobile Agent Team

## Context

安装 APK 会修改真实设备，属于 High 风险动作。现有 `confirmed=true` 只适合 Medium 动作，且
`PolicyEngine` 对 High 一律拒绝。直接让模型或客户端携带布尔值放行安装，无法证明用户看到的文件、
设备和包名与最终执行参数一致，也无法阻止确认被复用到另一项安装。

## Decision

- High 风险安装采用 `prepare → approve/submit` 两阶段协议。
- Prepare 仅做只读预检：路径必须位于 Runtime 配置的 APK 根目录内、是普通非符号链接 `.apk`、
  大小有界、ZIP/Manifest 有效；Runtime 计算 SHA-256，并从 APK Manifest 读取 package id。
- Prepare 返回不含绝对路径的影响摘要和短期 `approval_id`。授权绑定 device id、APK SHA-256、
  package id、是否替换现有应用与到期时间。
- MCP Host 必须向用户展示摘要并取得明确确认，才可提交 `approval_id + confirmed=true`。
- Approval 仅在当前 Runtime 内存中保存、十分钟过期、默认单次使用；相同 Idempotency-Key 可安全
  重取同一提交结果，不同 Key 或参数不得复用。
- 只有已校验并成功 claim 的 Approval 才能向 Policy Engine 提供内部 `high_risk_authorized=true`。
  外部 API、模型和 Skill Manifest 不能直接构造该内部授权位。
- 安装必须异步执行、持有 Device Lease 并绑定 Device Session；ADB 只使用固定 `install`/`-r`
  参数。命令返回后再次查询 package manager，验证目标包存在并记录版本与 APK SHA-256。
- 安装超时或连接中断可能已经产生副作用，使用 `ACTION_OUTCOME_UNKNOWN`，不得自动重试。

## Consequences

- High 风险动作不再由普通布尔确认直接放行，用户确认与具体文件和设备绑定。
- Runtime 重启会使未使用 Approval 失效；这是安全默认值。
- V1 只支持 Runtime 本地授权目录中的 APK，不下载 URL、不接受任意 ADB 参数。
- `replace_existing=true` 会在摘要中显式展示并使用固定 `adb install -r`；卸载仍不在本 ADR 范围。

## Alternatives Considered

- 复用 `confirmed=true`：无法绑定参数，也容易被模型或调用方误复用。
- 长期签名授权令牌：V1 没有账号与密钥管理，复杂度和攻击面过高。
- 安装后仅比较新包列表：错误 APK 可能先安装了非预期包，无法满足派发前验证要求。
- 调用任意外部 APK 工具：增加环境依赖；V1 使用受限的本地 Manifest 解析器。

## Follow-up

- 为桌面端增加可视化 High 风险确认卡片。
- 评估持久化审批审计，但不持久化可重放授权凭据。
- 卸载、清除数据等能力必须单独评审影响摘要与恢复语义。
