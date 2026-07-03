# ADR-0003: Android V1 使用 ADB-first

- Status: Accepted
- Date: 2026-07-03
- Deciders: Mobile Agent Team

## Context

V1 只需设备发现、截图、UI 树、应用启动和基础输入。引入完整 Appium 服务会增加 Node、Driver、Session 和版本管理成本。

## Decision

V1 使用受控 ADB Runner 与 UIAutomator hierarchy 实现 Android Adapter，不将 Appium 作为强依赖。上层接口保持 Provider 无关，未来可以加入 Appium/UiAutomator2 Provider。

## Consequences

- V1 依赖更少、问题定位更直接。
- 必须自行实现命令超时、错误映射、设备锁和 Observation 采集。
- WebView、复杂等待和部分自绘页面能力有限。
- 所有 ADB 调用集中在 Android Adapter 的批准模块。

## Alternatives Considered

- Appium-first：能力成熟，但初始依赖和 Session 管理较重。
- 自建 Android 设备端服务：长期控制力强，但 V1 开发和安装成本过高。
- 纯视觉坐标操作：适用面广但可靠性与可验证性不足。

## Follow-up

- 建立 ADB Runner 与 Fake Process Runner。
- 收集 UI 树缺失场景，作为引入视觉或 Appium Provider 的依据。
