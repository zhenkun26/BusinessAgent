-- ============================================
-- Migration 001: Prompt 版本管理(P2-1)
-- 适用于已在运行的环境(init.sql 已包含此表,新环境无需执行)
-- 执行: docker compose exec -T postgres psql -U agent enterprise_agent < deploy/migrations/001_prompt_versions.sql
-- ============================================

CREATE TABLE IF NOT EXISTS prompt_versions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'draft', -- draft / active / archived
    traffic_weight INTEGER DEFAULT 0,
    created_by VARCHAR(64) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP,
    UNIQUE (name, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_name ON prompt_versions(name);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_status ON prompt_versions(status);
