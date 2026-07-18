# ITER-0028 Agent Reliability & Recovery

> 状态：Completed
> 日期：2026-07-13

## 背景

“显示和亮度”真机任务暴露了底部手势区点击无效和 Provider 30 秒超时无诊断问题；
“进入蓝牙设置”已正确完成导航，却因标题、开关和开关文字同时匹配“蓝牙”而以
`TARGET_AMBIGUOUS` 结束。简单任务已经具备模型规划能力，但 Runtime 恢复与可观测性不足。

## 目标

- 使无副作用的定位和验证失败可以进入下一轮模型决策。
- 用前台 app/activity 和唯一 UI Selector 组合验证 `finish`。
- 在派发前拦截屏幕顶部系统区和底部手势区点击。
- 分类 Provider 错误，并对 retryable 请求最多重试一次。
- 为无效 Selector 提供不包含字段值的结构诊断。
- 避免因模型省略非安全关键审计说明而把已完成目标误判为失败。
- 在 Web/CLI 报告展示中间失败和 Provider 重试。

## 非目标

- 不重试可能已产生副作用的设备动作。
- 不将多匹配 Selector 宽松判定为成功。
- 不由 Runtime 自动滑动、改写模型决策或隐藏恢复轨迹。
- 不在本迭代接入平台精确 system insets。

## Contract 兼容性

新增 `AgentFinishCriteria`；`expected_foreground_app`、feedback 错误详情和 `provider_retry_count`
均为可选增量。已有有效 `expected_selector` 继续可用。TaskRun 状态枚举不变，但成功任务
可包含中间 failed round，该执行语义变化已由 ADR-0006 记录。无数据迁移。

## 已知风险

- 顶部和底部 4% 是启发式安全边距，可能保守拒绝个别真正可点击元素。
- Provider 重试可能增加一次计费请求；只在明确 retryable 时允许。
- 前台 Activity 在部分 App 中不稳定，因此保持可选，不由 Runtime 猜测。
