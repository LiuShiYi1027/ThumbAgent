# ITER-0004 Acceptance

> 状态：Completed
> 更新日期：2026-07-07

## 必选验收

- [x] UI Node、Selector 和 Match Result 具有版本化 Contract。
- [x] XML 解析不执行外部实体，并对节点数、深度和文本长度设限。
- [x] 支持 resource ID、text、content description、clickable 和祖先路径匹配。
- [x] exact 与 contains 语义明确，默认区分大小写。
- [x] 不存在返回 `TARGET_NOT_FOUND`，多个结果返回 `TARGET_AMBIGUOUS`。
- [x] 不可点击目标不会被静默转换为坐标点击。
- [x] bounds 必须有效、位于屏幕内，点击点位于目标 bounds 内。
- [x] `input.tap_element` 固定为 Medium 风险且需要确认。
- [x] Tool 使用最新 Observation 的 UI tree，不接受调用方伪造 bounds。
- [x] 等待具有超时和轮询上限，不形成无限循环。
- [x] 导航 Skill 通过目标 UI 证据验证成功。
- [x] 默认测试集不依赖真实设备。
- [x] 质量门禁和全部自动化测试通过。

## 真机安全验收

- [x] 从系统设置主页按语义进入一个设置子页面。
- [x] 目标元素唯一、可点击且 bounds 有效。
- [x] 页面标题或目标 UI 证据验证成功。
- [x] 未修改任何设置，未执行文本输入或裸坐标真机调用。

## 验证记录

### 自动化验证（2026-07-04）

| 命令 | 结果 |
| --- | --- |
| `make test`（python3.11 -m unittest discover） | 53 tests, OK |
| `python3.11 scripts/quality.py lint` | LINT OK |
| `python3.11 scripts/quality.py typecheck` | TYPECHECK OK |

覆盖范围：

- `test_ui_parser_locator.py`：XML 全文 DOCTYPE/ENTITY 拒绝、节点/深度/属性上限、bounds、visible/package 约束、语义定位和显式错误。
- `test_semantic_navigation.py`：tap_element 确认门禁、打开设置结果校验、跨 App Selector 拒绝、expected_selector 验证、等待上限和 Contract。
- `test_tool_runtime.py`：Tool 风险固定为 Medium、contract 版本常量、capability 拒绝、参数校验、确认门禁。
- `test_api_security.py`：POST JSON Content-Type、Bearer Token、Tauri/CLI Origin 规则。

### 真机验证（2026-07-07）

2026-07-04 已在真机开始验收，发现并修复以下厂商/多屏兼容性问题：

- `screencap` 在多 display 设备上先输出警告文本：现解析 SurfaceFlinger display ID，并显式选择 HWC display 0 重拍。
- `dumpsys window` 先列副屏焦点：现优先解析逻辑 display 0 的 `mFocusedApp`。
- UIAutomator 偶发空输出：只读采集最多重试一次，两次失败后安全停止。
- 系统设置可能恢复上次子页面：现通过 `android.settings.SETTINGS` Intent 打开设置根入口。

2026-07-07 重新连接 Android 16 真机并完成最终验收：

| 项 | 结果 |
| --- | --- |
| 设备 | `adb:A6TG025A13002156` / `BKQ_AN10` / Android 16 |
| 起点 | 系统设置主页，前台包名 `com.android.settings`，Activity `.HWSettings` |
| 目标 Selector | `text exact "显示和亮度"`，`resolve_clickable_ancestor=true`，限定 `com.android.settings` |
| 匹配节点 | `android:id/title` 文本节点“显示和亮度”，bounds `left=224 top=2511 right=1088 bottom=2587` |
| 点击目标 | 可点击祖先 `com.android.settings:id/dashboard_tile`，bounds `left=0 top=2465 right=1256 bottom=2633` |
| 验证证据 | 点击后前台 Activity `.Settings$DisplaySettingsActivity`，页面标题 `android:id/action_bar_title` 为“显示和亮度” |
| 安全结果 | 未点击开关、复选框、提交控件；未输入文本；未使用裸坐标真机调用 |

补充说明：单次 `input.tap_element` 的通用后置验证返回 `inconclusive`，但 `settings.navigate` Skill 随后通过 expected selector 在新 Observation 中验证页面标题，因此最终 Skill 结果为 `success=true`。
