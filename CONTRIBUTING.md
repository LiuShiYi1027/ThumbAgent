# Contributing to ThumbAgent

## 开发原则

ThumbAgent 采用 Skills-first、Contract-first 和本地优先的工程方式。开发者与 Agent 都必须遵守根目录 `AGENTS.md`。

## 工作流程

1. 阅读产品、技术方案和相关 ADR。
2. 将需求拆成边界清楚、可独立验证的任务。
3. 检查工作区，确认不会覆盖现有修改。
4. 先定义或复用 Contract，再实现功能。
5. 添加单元、Contract 或集成测试。
6. 运行与改动范围相称的验证。
7. 更新文档和必要的 ADR。
8. 提交时说明变更、验证结果与限制。

## 分支与提交

- 分支建议使用 `codex/<topic>` 或团队约定前缀。
- 一次提交只处理一个主题。
- Commit message 使用动词开头，表达结果，例如 `Add Android device discovery`。
- 不提交密钥、本地数据、设备截图、运行日志、数据库或构建产物。
- 不通过重写历史来解决多人协作冲突，除非维护者明确要求。

## Pull Request

PR 至少包含：

- 背景和目标
- 主要变更
- 测试与验证命令
- 风险和兼容性影响
- 截图或接口示例（适用时）
- 未解决问题

涉及架构、Contract、数据库或安全边界时，链接对应 ADR 或迁移说明。

## 代码审查重点

审查优先级如下：

1. 安全和数据风险
2. 正确性、状态一致性和取消语义
3. 架构边界与 Contract 兼容性
4. 测试覆盖和可诊断性
5. 性能与可维护性
6. 风格问题

## 本地验证

当前统一命令：

```text
make format
make lint
make typecheck
make test
make test-contract
make test-integration
make check
make run
```

默认使用 `python3.11`，可通过 `make PYTHON=/path/to/python ...` 覆盖。ITER-0001 的质量脚本使用标准库提供基础格式、架构 import、注解和语法检查；后续引入锁定开发依赖后由 Ruff 与 Pyright 接管同名命令。
