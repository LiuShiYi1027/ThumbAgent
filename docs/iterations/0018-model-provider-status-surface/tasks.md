# ITER-0018 任务拆解

> 状态：Completed
> 日期：2026-07-10

## 任务

- [x] 增加脱敏的模型 Provider 状态 helper。
- [x] 在 `RuntimeService` 中保存可注入的 `ModelProviderSettings`。
- [x] 增加 Runtime 同步状态查询方法。
- [x] 增加 `GET /v1/model-provider/status`。
- [x] 在 Web UI Demo 区域展示模型 Provider 只读状态。
- [x] 增加配置脱敏、Runtime 默认状态和 UI shell 测试。
- [x] 更新 README、技术方案和迭代索引。

## 实现说明

状态字段只包含：

- `enabled`
- `provider`
- `model`
- `base_url_configured`
- `api_key_ref_configured`
- `timeout_seconds`
- `status`

其中 `api_key_ref_configured` 只表示是否配置了密钥引用，不返回引用值本身。
