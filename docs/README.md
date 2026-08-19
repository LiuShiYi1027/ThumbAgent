# ThumbAgent 文档中心

本目录是项目文档的唯一正式存放位置。根目录只保留项目入口、Agent 指令和贡献指南。

## 导航

- [产品](./product/)
- [架构](./architecture/)
- [工程规范](./engineering/)
- [迭代](./iterations/README.md)
- [架构决策](./adr/README.md)
- [发布记录](./releases/README.md)
- [归档](./archive/README.md)
- [文档与迭代规范](./documentation-guide.md)

## 文档状态

- `Draft`：讨论中，不作为实现依据。
- `Active`：当前有效，是相应主题的真源。
- `Superseded`：已由新文档替代，必须链接替代文档。
- `Archived`：仅保留历史，不再维护。

发生冲突时，当前 `Active` 文档与最新 `Accepted` ADR 优先；若二者冲突，必须先新增 ADR 澄清再实现。
