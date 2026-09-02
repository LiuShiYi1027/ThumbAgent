-- 目的：自定义 Skill 生命周期审计事件持久化（ITER-0062 / ADR-0021 决策 9）。
-- 前置版本：0003_custom_skills（custom_skills 表）。
-- 升级步骤：创建追加式 skill_audit 表与按 skill_id 查询的索引。
-- 恢复策略：备份数据库后 DROP TABLE skill_audit 并删除本 revision 记录。
CREATE TABLE skill_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    skill_version TEXT,
    document_sha256 TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_skill_audit_skill_id ON skill_audit(skill_id);

INSERT INTO schema_migrations(revision) VALUES ('0004_skill_audit');
