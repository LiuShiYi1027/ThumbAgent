# ITER-0003 Acceptance

> 状态：Active  
> 更新日期：2026-07-03

## 必选验收

- [x] Action 和 Skill Result 具有 Schema 与 Contract 测试。
- [x] 每个 Tool 声明 Capability、风险和幂等属性。
- [x] Low Tool 可执行，Medium Tool 未确认时被 Policy 拒绝。
- [x] 模型或调用方不能降低 Tool 注册风险。
- [x] 动作结果包含前后 Observation、时间、状态和验证结果。
- [x] 设备结果不确定时不会自动重试。
- [x] Android Adapter 支持 launch、Back、Home 和受边界校验的 tap。
- [x] `app.open@1` 通过动作后前台包名验证，不以 ADB 退出码单独判成功。
- [x] Runtime API 不允许任意 Tool 名或任意 Shell 参数。
- [x] Fake Adapter 覆盖成功、Policy 拒绝、未知 Tool 和验证失败；Capability 缺失由 Tool Runtime 统一拒绝。
- [x] 默认测试集不依赖真实设备。
- [x] 质量门禁和全部自动化测试通过。

## 真机安全验收

- [x] 打开系统设置并验证前台包名。
- [x] 执行 Back 与 Home 后均生成前后 Observation。
- [x] 未对真机执行 tap、输入或系统设置修改。

## 验证记录

验证日期：2026-07-03  
环境：macOS arm64、Python 3.11、ADB 37.0.0、Android 16 真机

- `make check`：通过；33 个无设备测试全部通过。
- Tool Registry：公开 4 个固定 Tool，风险和幂等属性符合规范。
- `app.open@1`：从桌面启动系统设置，动作后前台包名验证为 `com.android.settings`。
- Back：从系统设置返回桌面，保留前后 Observation，验证状态为 `inconclusive`。
- Home：在桌面执行，保留前后 Observation，验证状态为 `inconclusive`。
- HTTP：`GET /v1/tools` 与 `POST /v1/skills/app.open/invoke` 真机调用通过。
- 安全：未注册 `shell.execute` 被拒绝；Medium `input.tap` 未确认被拒绝；未在真机执行 tap。
- 证据仅进入被 Git 忽略的本地 `data/`。
