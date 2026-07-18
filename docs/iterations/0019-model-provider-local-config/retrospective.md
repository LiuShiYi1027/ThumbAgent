# ITER-0019 复盘

> 状态：Completed
> 日期：2026-07-10

## 完成内容

本迭代让模型 Provider 状态从“只能代码注入”前进到“Runtime 可读取本地配置”。用户后续可以通过本地配置文件表达是否启用模型 Provider、provider 类型、base URL、模型名和密钥引用。

## 关键取舍

- 配置文件只保存 `api_key_ref`，不保存真实 key。
- 环境变量 resolver 只允许 `MOBILE_AGENT_MODEL_SECRET_*` 前缀，避免把任意系统环境变量变成密钥读取通道。
- 默认 Runtime 加载配置但不切换默认 Planner，避免在未完成显式授权、错误展示和数据边界说明前调用云模型。
- 修正 `MODEL_UNAVAILABLE` details，只返回是否存在密钥引用，不返回引用原文。

## 后续建议

下一步可以做“显式模型启用到 Agent Runner 的受控接线”：

- Runtime 启动时构造 Planner，但失败要清楚显示 `MODEL_UNAVAILABLE`；
- Web UI 增加模型启用风险说明；
- 任务报告中记录 Planner source，但不记录 prompt、密钥或完整模型响应；
- 设计正式 Keychain SecretResolver，替换开发预览 env resolver。
