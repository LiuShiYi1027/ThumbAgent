CREATE TABLE custom_skills (
    skill_id TEXT NOT NULL,
    skill_version TEXT NOT NULL,
    document_json TEXT NOT NULL,
    document_sha256 TEXT NOT NULL,
    derived_risk TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (skill_id, skill_version)
);

CREATE INDEX idx_custom_skills_skill_id ON custom_skills(skill_id);

INSERT INTO schema_migrations(revision) VALUES ('0003_custom_skills');
