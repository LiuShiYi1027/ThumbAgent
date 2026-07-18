# ITER-0005 Retrospective

> 状态：Active
> 更新日期：2026-07-08

## 实际交付

- 新增 `input.swipe`：Medium 风险、默认确认、受限方向/距离/时长和安全滚动区域。
- 新增 `input.text`：Medium 风险、默认确认、只允许明确可编辑目标和非敏感短文本。
- 新增有界语义滚动查找：Observe → match → swipe → settle → Observe，支持最大滚动次数、超时、无进展、目标不唯一和设备断连错误。
- 新增 `settings.scroll_navigate` Skill 与 Runtime API。
- 兼容 Android/HyperOS 真机输入差异：tap 使用 `input touchscreen tap`，swipe 使用 plain `input swipe`，Settings 启动增加 `NEW_TASK | CLEAR_TOP` flags。

## 验收结果

- 默认质量门禁通过：`make check` 62 tests OK，`git diff --check` OK。
- Android 真机 `adb:5f37fd7` 滚动导航 E2E 通过：目标“显示与亮度”初始不可见，滚动后点击进入，并通过 action bar 标题验证成功。
- 文本输入真机 E2E 未执行：系统设置搜索入口未暴露明确安全的 `EditText`，不强行在真实设备敏感页面输入。

## 计划偏差

- 原计划希望在系统设置中完成安全文本输入真机验收，但厂商系统页面结构不稳定，且未暴露可安全验证的 `EditText`。
- 为避免为了验收而触达敏感页面，本迭代仅保留文本输入自动化测试和策略覆盖，真机 E2E 移入后续 demo/test app。

## 有效做法

- 继续坚持 Tool/Skill 通过 Policy 和 Device Gateway，不暴露裸 ADB 命令。
- 真机验证只做可撤销、无副作用路径；遇到厂商兼容性问题后先记录证据，再收敛为 Adapter 层差异。
- 滚动查找采用保守边界和 settle wait，避免动画期间误判。

## 问题与根因

- HyperOS 对 `input tap` 返回码和真实触发效果不一致，需要显式 `touchscreen` source。
- 系统设置页面不适合作为文本输入长期验收载体：页面结构、搜索入口和输入焦点行为会随厂商变化。

## 长期文档回写

- 更新错误与诊断规范，补充 UI 目标相关错误码。
- 本迭代未改变 Tool/Skill 分层或安全信任模型，不需要 ADR。

## 后续行动

- 后续提供一个极小 Android demo/test app，专门用于非敏感 `EditText` 输入 E2E。
- 下个迭代进入 Task Runner 与 Evidence Report，让 Skill 执行结果沉淀为可审计任务报告。
