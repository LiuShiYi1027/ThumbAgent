# Mobile Agent

面向 AI Agent 的本地优先、跨平台移动设备 Skills 平台。

## 当前开发

项目处于 ITER-0001 Runtime Foundation。使用 Python 3.11+：

```bash
make check
make run
```

Runtime 默认监听 `127.0.0.1:8765`，提供 `/v1/health`、`/v1/devices` 和 `POST /v1/devices/{device_id}/observe`。

ITER-0003 增加 `GET /v1/tools`、`POST /v1/tools/{tool_id}/invoke` 和 `POST /v1/skills/app.open/invoke`。`input.tap` 属于 Medium 风险，默认需要明确确认。

ITER-0004 增加安全 UI hierarchy 解析、语义 Selector、`input.tap_element` 和 `POST /v1/skills/settings.navigate/invoke`。语义点击属于 Medium 风险，匹配不唯一时拒绝执行。

## 产品文档

- [产品定位](./docs/product/positioning.md)
- [第一版产品方案](./docs/product/solution-v1.md)
- [V1 技术方案](./docs/architecture/technical-design-v1.md)

## 工程规范

- [Agent 开发入口](./AGENTS.md)
- [贡献指南](./CONTRIBUTING.md)
- [文档与迭代规范](./docs/documentation-guide.md)
- [工程开发规范](./docs/engineering/development.md)
- [Contract 与 API 演进规范](./docs/engineering/contract-versioning.md)
- [Capability 模型](./docs/architecture/capability-model.md)
- [Skill 开发规范](./docs/engineering/skill-development.md)
- [可靠性与执行语义](./docs/architecture/reliability-model.md)
- [数据与迁移规范](./docs/engineering/data-migrations.md)
- [错误与诊断规范](./docs/engineering/error-handling.md)
- [架构边界](./docs/architecture/rules.md)
- [测试规范](./docs/engineering/testing.md)
- [安全规范](./docs/engineering/security.md)
- [多 Agent 协作规范](./docs/engineering/agent-collaboration.md)
- [架构决策记录](./docs/adr/README.md)
- [迭代索引](./docs/iterations/README.md)
