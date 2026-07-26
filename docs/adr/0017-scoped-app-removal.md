# ADR-0017: 应用卸载独立确认数据删除影响

- Status: Accepted
- Date: 2026-07-26
- Deciders: Mobile Agent Team

## Context

卸载会移除真实设备上的应用，并可能不可逆地删除应用数据。虽然 ADR-0016 已建立 High 风险动作的
范围绑定授权机制，但 APK 文件摘要和替换语义不能表达卸载对象、版本、系统应用保护与数据保留影响。
普通 `confirmed=true` 或复用安装 Approval 都不能证明用户确认了正确的卸载对象。

## Decision

- `app.uninstall@1` 是 High 风险、unsafe 幂等的独立 Capability。
- 使用 `prepare → approve/submit` 两阶段协议；Prepare 只读取设备包管理器，不执行卸载。
- Prepare 返回应用标识、版本、安装来源、启用状态、系统应用判定、`keep_data` 和明确的数据删除提示。
- 系统应用或无法明确判定为非系统应用的目标在 Prepare 阶段拒绝。
- Approval 绑定 device id、应用标识、版本和 `keep_data`，十分钟过期、单次使用并只保存在 Runtime 内存。
- Submit 必须携带新的明确确认和 Idempotency-Key；只有成功 claim 的 Approval 才能提供内部
  `high_risk_authorized=true`。
- Android Adapter 只执行固定 `adb uninstall [ -k ] <validated-package-id>` 参数数组。
- 异步任务持有 Device Lease 并绑定 Device Session；命令返回后通过 package manager 验证目标包缺失。
- 超时或连接中断映射 `ACTION_OUTCOME_UNKNOWN`，不得自动重试。

## Consequences

- 外部 Agent 必须先展示数据删除影响，再请求一次独立用户确认。
- V1 不支持系统应用卸载、静默绕过设备管理策略、批量卸载、降级、清除其他应用数据或权限修改。
- `keep_data=true` 只表达向平台请求保留数据；成功验证只证明包已移除，不读取或暴露应用私有数据。
- 新增 Contract、Capability、Task 类型、REST 与 MCP Tool，属于兼容性新增，无需数据库迁移。

## Alternatives Considered

- 复用 APK 安装 Approval：绑定对象和用户影响不同，容易造成错误授权。
- 仅使用 `confirmed=true`：无法证明用户看到了应用版本和数据删除摘要。
- 根据包名前缀判断系统应用：厂商包名不稳定，安全性不足。
- 卸载超时后自动重试：重复写动作的结果不可确定，不符合可靠性模型。

## Follow-up

- 真机验证普通测试应用的删除与保留数据两种语义。
- 桌面端后续增加统一 High 风险影响摘要卡片。
- 清除数据必须作为新的独立 High 风险能力评审，不能借用卸载 Approval。
