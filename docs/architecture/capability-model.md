# Capability 模型

> 状态：Active
> 更新日期：2026-07-15

## 1. 目的

Capability 表达某台设备在当前连接、权限和运行状态下可以提供的能力。上层不得仅根据 `platform == android` 推断能力存在。

## 2. 核心原则

- Capability 是运行时事实，不是产品承诺。
- 平台、设备、连接方式、授权和当前状态都可能影响 Capability。
- Capability 缺失必须显式返回，不能静默降级成不可靠动作。
- Tool 和 Skill 在执行前解析 Capability，执行期间设备状态变化时重新校验。

## 3. 命名

使用稳定的 `domain.verb`：

```text
device.inspect
screen.observe
app.launch
input.tap
input.text
input.swipe
navigation.back
navigation.home
logs.collect
performance.snapshot
```

不在 ID 中放平台名或版本，例如不用 `android.adb.tap`。

## 4. Capability Descriptor

```yaml
id: app.launch
version: 1
availability: available
risk: low
idempotency: conditional
verification: required
requirements:
  device_states: [online, interactive]
limitations:
  - app identifier must be known
provider:
  adapter: android
  implementation: adb
```

字段含义：

- `id`：稳定语义标识。
- `version`：Capability Contract 主版本。
- `availability`：`available | unavailable | degraded | unknown`。
- `risk`：注册策略给出的最低风险等级。
- `idempotency`：`safe | conditional | unsafe`。
- `verification`：`required | supported | unavailable`。
- `requirements`：设备状态、授权或配套能力。
- `limitations`：机器和用户都可理解的限制。
- `provider`：诊断信息，不进入上层业务判断。

## 5. 解析流程

```text
Skill required capabilities
→ Device advertised capabilities
→ Current device/session state
→ Policy restrictions
→ Effective capabilities
```

执行前返回以下之一：

- `allowed`：能力存在且策略允许。
- `confirmation_required`：能力存在，但需要确认。
- `temporarily_unavailable`：锁屏、离线等状态导致暂不可用。
- `unsupported`：Adapter 不提供能力。
- `degraded`：可执行但存在已知限制，调用方必须明确接受。

## 6. 平台映射

Adapter 将平台实现映射为统一 Capability：

```text
Android ADB input tap   ┐
iOS XCTest tap          ├→ input.tap@1
Harmony driver tap      ┘
```

统一的是语义和 Contract，不要求不同平台具有相同成功率、权限或性能。差异通过 availability、requirements 和 limitations 表达。

## 7. 动态能力

以下情况必须刷新 Capability：

- 设备连接、断开或重新授权
- 设备锁定、解锁或用户切换
- Adapter/driver 安装或版本变化
- 权限变化
- 应用进入不支持的上下文
- Runtime 恢复设备 Session

Capability 快照需要时间戳，不得无限缓存。

## 8. 版本兼容

- 同主版本可新增可选限制和诊断字段。
- 改变输入语义、风险或验证保证时提升主版本。
- Skill 必须声明所需主版本，例如 `screen.observe@1`。
- Adapter 可以同时提供多个主版本，但不得用较低语义冒充较高版本。

## 9. V1 最小能力集

```text
device.inspect@1
screen.observe@1
app.launch@1
input.tap@1
input.text@1
input.swipe@1
navigation.back@1
navigation.home@1
logs.collect@1
performance.snapshot@1
```

ITER-0001 只需实现 `device.inspect@1` 及设备发现所需内部能力，其余在后续迭代启用。

ITER-0035 起，Runtime 使用平台无关 Capability Catalog 保存基础八项能力的风险、幂等性、验证、
要求和限制。Tool Registry 只保存 Tool→Capability 映射，并从 Catalog 派生风险与幂等性；Policy
Engine 仍在执行时独立授权。DeviceInspection 将 Adapter 当前 advertised capabilities 与
DeviceAvailability 合并：ready 映射 available/unsupported，busy 将已广告能力映射为
temporarily_unavailable，offline/unauthorized 映射 unknown，禁止根据 platform 猜测支持。

ITER-0036 增加 `logs.collect@1`。它是 Medium 风险、safe 幂等的工程诊断能力，只允许采集有界快照；
原始平台日志必须先脱敏并保存为本地 Artifact。关联底层 Tool 不允许通过通用 UI Action 入口直接
调用，只能由声明该 Tool allowlist 的 `device.logs.collect` Skill 编排。

ITER-0038 增加 `performance.snapshot@1`。它是 Low 风险、safe 幂等的聚合只读能力，只保留总
CPU、内存、电池与系统负载；进程、应用和平台原始诊断输出不进入 Capability 消费者或 Artifact。

## 10. 测试要求

- 每个 Adapter 有 Capability Contract 测试。
- unavailable、degraded 和状态变化必须有测试。
- Tool 缺少 Capability 时不能调用底层 Adapter 方法。
- 新增 Capability 必须登记风险、幂等和验证属性。
