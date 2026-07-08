# ITER-0004 Retrospective

> 状态：Completed
> 更新日期：2026-07-07

## 实际交付

交付了完整的语义导航闭环：

- **Contract**：`ui-node`、`ui-selector`、`ui-match`、`navigation-result` 四个版本化 JSON Schema（v1.0.0），与 `action-result`、`observation` 等已有 Contract 通过 `$ref` 衔接。
- **解析**：`UiHierarchyParser` 拒绝 DOCTYPE/ENTITY，限制 5 MiB / 10000 节点 / 64 层 / 1024 字符属性，bounds 用正则严格校验。
- **定位**：`UiLocator` 支持 resource_id / text / content_description 三种策略与 exact / contains 两种匹配（默认区分大小写），支持 clickable 过滤、ancestor_path 路径约束和 resolve_clickable_ancestor 安全祖先解析；不唯一返回 `TARGET_AMBIGUOUS`，不存在返回 `TARGET_NOT_FOUND`，不可点击返回 `TARGET_NOT_CLICKABLE`，超出屏幕返回 `TARGET_OUT_OF_BOUNDS`。
- **Tool**：`input.tap_element` 固定 Medium 风险、需 confirmed；从执行前 Observation 的 UI tree 解析节点，不接受调用方伪造 bounds；`wait_for_element` 超时上限 30 s、轮询可配、不无限循环。
- **Skill**：`SettingsNavigateSkill` 打开设置 → 等待目标 → 确认点击 → 等待 expected_selector 验证，返回含 verified_observation 与 verified_node 的 NavigationResult。
- **API**：`POST /v1/skills/settings.navigate/invoke` 与 `POST /v1/tools/{tool_id}/invoke` 暴露到 loopback HTTP。
- **安全修复**：设置导航强制校验前台应用和节点 package；隐藏节点不能作为验证证据；XML 声明全文拒绝；Local API POST 使用短期 Bearer Token、Origin 和 Content-Type 校验。
- **真机兼容修复**：支持多 display 截图选择、主屏前台焦点解析、UIAutomator 一次有界重试和 Settings 根 Intent。
- **测试**：53 tests 全通过，lint / typecheck 通过。

## 验收结果

必选自动化验收 13/13 全部通过（见 acceptance.md）。2026-07-07 在 Android 16 真机 `adb:A6TG025A13002156` 上完成真机安全验收 4/4：从设置主页按语义进入“显示和亮度”，目标元素唯一并解析到可点击祖先，页面标题验证成功，且未修改设置、未输入文本、未执行裸坐标真机调用。因此迭代状态为 Completed。

## 计划偏差

原实现完成后发现四项必须修复的问题：跨 App 误点击风险、隐藏节点误验证、DOCTYPE 前缀绕过和 Local API 可伪造确认。现已修复并增加回归测试。真机验收还暴露了多 display 截图警告、主副屏焦点、UIAutomator 偶发空输出和设置页面恢复等厂商兼容性差异，均已修复并完成回归验证。

## 有效做法

- 先定义 Contract 再写实现，`UiSelector.from_dict` 的白名单校验和 `Bounds.__post_init__` 在入口处拦截非法输入，使后续逻辑只需处理合法数据。
- 解析器与定位器分离：`UiHierarchyParser` 只负责把不可信 XML 转为有界 `UiNode` 列表，`UiLocator` 只负责确定性匹配，两者均可独立用录制样本测试，不依赖真实设备。
- tap_element 始终从 before-observation 的 UI tree 解析，而非接受调用方传入的坐标或 bounds，从架构上杜绝了伪造点击点。
- resolve_clickable_ancestor 显式且可审计：matched_node 与 target_node 都进入 UiMatch，调用方能看到解析过程而非黑箱坐标。

## 问题与根因

**问题**：厂商 ROM 与多屏设备会让“看似标准”的 ADB 输出出现非标准细节，例如 `screencap` 前置警告文本、`dumpsys window` 先列副屏焦点，以及 UIAutomator 偶发空输出。

**根因**：Adapter 初版把 Android 工具输出视为单一主屏和稳定输出，缺少对多 display、输出前缀和间歇性空响应的有界兼容处理。

**处理**：截图改为识别 PNG 起点并在多 display 时选择 HWC display 0；前台应用解析优先 display 0；UI hierarchy 采集只读重试一次；设置启动改用 `android.settings.SETTINGS` 入口，避免恢复上次子页面。

## 长期文档回写

无架构变更需要新增 ADR。本次在已有 `0002-tool-skill-model` ADR 框架内新增了一个 Tool 和一个 Skill，未改变分层或依赖方向。`docs/architecture/capability-model` 和 `skill-development` 的现有描述已覆盖 tap_element 与 settings.navigate 的定位方式。

## 后续行动

- **下一迭代候选**：文本输入（input.text）、滑动（input.swipe）与基于语义的长按，需各自新增 Medium/High 风险 Tool 和对应 Skill。
- **可选增强**：为 UiLocator 增加 partial_match 容错（如 resource_id 包包名前缀时的归一化），待更多真机数据反馈后再决定是否需要。
- **E2E 资产**：后续可把真机验收脚本沉淀为显式 `device_e2e` 命令，但不得进入默认快速测试集。
