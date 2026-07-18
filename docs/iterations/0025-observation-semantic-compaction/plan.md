# ITER-0025 Observation Semantic Compaction & Redaction

> 状态：Completed
> 日期：2026-07-13

## 背景

ITER-0024 真机 E2E 已能识别无效滑动并把反馈交给模型，但任务仍在六轮后以 `NO_PROGRESS` 结束。
复盘完整 UI Tree 发现，“显示和亮度”在第 2、3、4 轮已经可见；模型收到的 `ui_summary` 却被前 30 个
FrameLayout、容器、图标和箭头节点占满，目标文本被截断。摘要中还出现了掩码手机号，暴露出模型边界前缺少
标识符脱敏。

## 目标

- 让有限摘要预算优先承载用户可见、可操作的语义内容。
- 保留文本节点与可点击祖先的关系，支持模型生成 `input.tap_element`。
- 向模型明确摘要候选数量和是否截断。
- 在 UI 文本进入模型 Prompt 和任务摘要前脱敏常见标识符。
- 不改变本地完整 UI Tree 的证据和确定性 Selector 行为。

## 实现

### Semantic compaction

- 仅将包含 `text` 或 `content_description` 的可见节点作为候选。
- 过滤仅有 resource ID 的布局容器、图标和箭头等结构噪声。
- 以文本、可操作性和屏幕位置排序，并对相同语义节点去重。
- 每项增加 `clickable_ancestor`，表示 `resolve_clickable_ancestor=true` 是否有可用目标。
- 保持最多 30 项，并增加 `ui_summary_total_candidates` 与 `ui_summary_truncated`。

### Redaction

模型侧摘要在生成阶段过滤：

- 中国大陆手机号；
- 星号掩码手机号；
- 邮箱地址；
- 12～19 位长数字标识符。

替换值使用固定占位符，不把原文写入 Agent step result 或模型 Prompt。亮度百分比等普通短数字保持可用。
完整 UI Tree 仍作为本地证据保存，不直接发送给模型。

## Contract 兼容性

`AgentObservationSummary` 向后兼容地增加可选元数据，`ui_summary` item 向后兼容地增加可选
`clickable_ancestor`。既有字段、类型和含义不变，不需要主版本升级或数据迁移。

## 验收

- 30 个以上结构节点不能挤掉后续可见目标文本。
- “显示和亮度”进入模型摘要，并标记存在可点击祖先。
- 掩码手机号、完整手机号、邮箱和长数字标识不会进入模型请求。
- 摘要能报告候选总数和截断状态。
- 默认测试不依赖真实设备、网络或模型密钥。
- `make check` 通过。

## 已知限制

- 正则脱敏只能覆盖已知标识符格式，不能识别所有姓名、地址或业务隐私文本。
- 当前仍使用 UI hierarchy，不处理纯 Canvas、游戏或完全视觉化界面。
- 摘要优先级是确定性通用规则，后续需要用版本化 Agent 评测验证不同应用上的召回率。
- 真机 E2E 需要重启 Runtime 后显式执行，不进入默认测试集。
