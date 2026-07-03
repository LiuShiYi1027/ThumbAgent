# ITER-0001 Tasks

> 状态：Active  
> 更新日期：2026-07-03

| ID | 状态 | Owner | 任务 | 主要范围 |
| --- | --- | --- | --- | --- |
| TASK-0001-01 | done | Codex | 建立 Monorepo 与统一开发命令 | 根配置、`runtime/`、`contracts/` |
| TASK-0001-02 | done | Codex | 定义最小 Device Contract | `contracts/schemas/`、生成类型策略 |
| TASK-0001-03 | done | Codex | 建立 Python Runtime 与健康检查 | Runtime package、API、配置 |
| TASK-0001-04 | done | Codex | 定义 Device Adapter 与 Fake Adapter | Domain port、test fake |
| TASK-0001-05 | done | Codex | 实现安全 ADB Runner | Android Adapter、process abstraction |
| TASK-0001-06 | done | Codex | 实现 Android 设备发现 | ADB parser、Device mapping |
| TASK-0001-07 | done | Codex | 建立测试、Lint 与类型检查门禁 | 测试配置、统一命令、CI 基础 |
| TASK-0001-08 | done | Codex | 完成迭代集成验证与文档 | 验收、开发说明、复盘 |

## 协作约束

- `TASK-0001-02` 的 Contract 由唯一 Owner 修改真源。
- `TASK-0001-04` 必须在 `TASK-0001-02` 合并后稳定 Adapter 返回类型。
- `TASK-0001-05` 和 `TASK-0001-06` 可以按 Runner 与解析器边界并行，但不得各自定义 Device。
- 每项任务完成后更新状态和实际验证，不新增未登记范围。
