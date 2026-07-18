# ITER-0017 Retrospective

> 状态：Active
> 更新日期：2026-07-09

## 实际交付

- 新增 `ModelProviderSettings`。
- 新增 `SecretResolver` 端口。
- 新增 `build_planner_from_settings` 配置门。
- 默认配置返回 `RuleBasedPlanner`，不触发 secret lookup。
- 显式启用 OpenAI-compatible 配置时，使用 `api_key_ref` 通过注入 resolver 获取密钥并构造 Planner。
- README 与技术方案同步记录“默认关闭、显式启用”的 Provider 边界。

## 验收结果

- 定向测试 8 tests OK。
- 全量 `make check` 98 tests OK，lint/typecheck OK。

## 计划偏差

- 未把配置门接入默认 Runtime，符合本迭代范围。
- 未读取真实环境变量、配置文件或 Keychain，避免提前扩大安全边界。

## 有效做法

- 配置对象只保存 `api_key_ref`，不保存原始密钥。
- secret resolver 使用注入端口，便于后续接 Keychain，也便于测试。
- 默认关闭时不访问 secret resolver，降低意外触发云模型的风险。

## 问题与根因

- 目前还没有用户可操作的配置界面或配置文件加载逻辑；这是下一步的显式授权问题。

## 长期文档回写

- README 和技术方案已记录 Provider 配置门。
- 本迭代未改变默认 Runtime 行为、持久化 Schema 或平台 Adapter，不需要 ADR。

## 后续行动

- 下一步可以设计本地模型配置文件格式，但密钥仍应通过 Keychain 引用。
- 也可以先做 Web UI 中的“模型未启用/已配置”只读状态展示。
