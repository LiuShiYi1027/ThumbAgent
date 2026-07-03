# ITER-0002 Tasks

> 状态：Active  
> 更新日期：2026-07-03

| ID | 状态 | Owner | 任务 | 主要范围 |
| --- | --- | --- | --- | --- |
| TASK-0002-01 | done | Codex | 定义 Observation 与 Artifact Contracts | `contracts/schemas/`、领域模型 |
| TASK-0002-02 | done | Codex | 实现本地 Artifact Store | 原子写入、哈希、路径约束 |
| TASK-0002-03 | done | Codex | 扩展 Device Adapter 与 Fake Adapter | Observation port、测试 fake |
| TASK-0002-04 | done | Codex | 实现 Android Observation 采集 | screenshot、display、foreground、UI tree |
| TASK-0002-05 | done | Codex | 扩展 Runtime HTTP API | observe endpoint、错误映射 |
| TASK-0002-06 | done | Codex | 自动化测试与真机验收 | Contract、解析、集成、设备验证 |
| TASK-0002-07 | done | Codex | 完成验收与复盘 | 文档和下一迭代建议 |

## 协作约束

- Contract 由 `TASK-0002-01` 唯一修改真源。
- Artifact Store 不依赖 Android Adapter。
- Android Adapter 不直接决定 Artifact 的保留策略。
- HTTP 层只调用 Runtime Service，不直接读取设备或文件。
