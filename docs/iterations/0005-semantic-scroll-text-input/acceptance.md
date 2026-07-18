# ITER-0005 Acceptance

> 状态：Completed
> 更新日期：2026-07-08

## 必选验收

- [x] 滚动与文本输入相关输入输出具有版本化 Contract，兼容性结论已记录。
- [x] `input.swipe` 固定为 Medium 风险，默认需要确认。
- [x] `input.swipe` 只接受受限方向、距离、持续时间和屏幕安全区域，不接受调用方伪造任意危险坐标。
- [x] `input.swipe` 执行后重新 Observe，并返回前后 Observation 引用和动作结果。
- [x] `input.text` 固定为 Medium 风险，默认需要确认。
- [x] `input.text` 只向明确可编辑的目标输入；无法确认目标可编辑时拒绝。
- [x] `input.text` 对文本长度、空白、控制字符和敏感模式做限制。
- [x] 密码、验证码、支付、账号安全或其他高风险文本输入场景被拒绝。
- [x] 语义滚动查找具有最大滚动次数、总超时和无进展阈值，不形成无限循环。
- [x] 语义滚动查找在目标不存在、目标不唯一、滚动无进展和设备断连时返回明确错误。
- [x] 安全示范 Skill 通过结构化 UI 证据验证成功，不仅依赖底层命令退出码。
- [x] 默认测试集不依赖真实设备、网络或模型服务。
- [x] 质量门禁和全部自动化测试通过。

## 真机安全验收

- [x] 在 Android 真机上完成一次有界语义滚动查找，目标元素不在初始首屏。
- [x] 滚动过程中未点击开关、复选框、删除、确认、提交或支付控件。
- [ ] 在 Android 真机上完成一次安全文本输入，文本为非敏感短文本且不会自动提交。（Deferred：移入后续 demo/test app 验证）
- [ ] 输入后通过 UI hierarchy 或前台页面结构验证文本结果。（Deferred）
- [x] 验收结束后设备可恢复到安全状态，未修改系统关键设置。

## 验证记录

### 自动化验证

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_tool_runtime runtime.tests.test_android_adapter -v` | 17 tests, OK |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_tool_runtime -v` | 13 tests, OK |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_semantic_navigation -v` | 8 tests, OK |
| `make check` | 62 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

计划覆盖：

- Contract 版本与 Schema 校验。
- Swipe 参数边界、策略确认、屏幕边界和 Adapter 参数数组。
- Text 参数边界、可编辑目标校验、敏感文本拒绝和后置验证。
- 语义滚动查找的成功、找不到、不唯一、无进展、超时、设备断连。
- `settings.scroll_navigate` 的滚动查找、点击和 expected selector 验证。
- Runtime API 认证、参数校验和错误映射。

### 真机验证

### 真机验证（2026-07-08）

已连接 Android 16 真机：

| 项 | 结果 |
| --- | --- |
| 设备 | `adb:5f37fd7` / `2509FPN0BC` / Android 16 |
| 只读观察 | 通过，成功打开系统设置主页并读取 UI hierarchy |
| 前台应用 | `com.android.settings` / `.MiuiSettings` |
| 输入注入 | 用户开启 USB 调试安全设置后，`adb shell input tap/swipe` 返回 0 |
| 兼容修复 | tap 需要 `input touchscreen tap` 才能真正触发行点击；swipe 使用 plain `input swipe` 更稳定 |
| Settings 根入口 | `android.settings.SETTINGS` 增加 `NEW_TASK | CLEAR_TOP` flags，避免恢复到 `.SubSettings` 子页 |
| 滚动参数 | 语义滚动使用安全滚动区、较长 duration 和 settle wait，避免 HyperOS 动画期间误判 `NO_PROGRESS` |
| 滚动导航 E2E | 通过：起始页不包含“显示与亮度”，滚动后匹配列表项，点击进入 `.SubSettings`，并用 action bar 下“显示与亮度”标题验证 |
| 文本输入 E2E | 未执行：系统设置搜索入口未暴露安全 `EditText`，不强行进入敏感页面输入 |

滚动导航证据摘要：

- `pre_target_visible=false`，目标“显示与亮度”不在初始首屏。
- `settings.scroll_navigate` 返回 `success=true`。
- `tap_action.status=succeeded`，`tap_action.verification=inconclusive`。
- `verified_node.resource_id=com.android.settings:id/action_bar_title_expand`，文本为“显示与亮度”。
- 全程未点击开关、复选框、删除、确认、提交或支付控件。

后续若要完成文本输入真机验收，需要提供一个明确安全、非敏感、不会自动提交的 `EditText` 页面，例如测试 App 或专用 demo 页面。
