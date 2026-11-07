-- C03 managed baseline v1: schema only. Apply via app.core.db_bootstrap.
-- Never edit after application; append a new manifest migration instead.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE NOT NULL,
    username VARCHAR(128) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(32) NOT NULL,  -- salesperson / customer_service / finance / manager / admin
    department VARCHAR(64),
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt 哈希(生产必需)
    sso_issuer VARCHAR(512),
    sso_subject VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    original_query TEXT,
    status VARCHAR(32) DEFAULT 'pending',  -- pending / running / completed / failed
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    token_count INTEGER DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS approval_requests (
    approval_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id),
    requester_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    batch_id VARCHAR(64),
    operation_type VARCHAR(64) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    summary TEXT,
    prefill_payload JSONB,
    approver_roles JSONB NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',  -- pending / approved / rejected / timeout / approved_pending_reauth / executed
    approver_id VARCHAR(64) REFERENCES users(user_id),
    comment TEXT,
    requester_token TEXT,  -- 加密存储, 审批恢复时使用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    session_id VARCHAR(64),
    user_id VARCHAR(64),
    tool_name VARCHAR(64),
    input_summary TEXT,
    output_summary TEXT,
    success BOOLEAN,
    latency_ms INTEGER,
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_memories (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    memory JSONB NOT NULL,
    memory_type VARCHAR(32),  -- preference / fact / context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saga_transactions (
    saga_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id),
    batch_id VARCHAR(64),
    status VARCHAR(32) DEFAULT 'running',  -- running / completed / compensated / failed
    actions JSONB NOT NULL,  -- 计划执行的动作
    executed_actions JSONB,  -- 已执行的动作
    compensation_results JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id),
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    message_id VARCHAR(64),
    feedback_type VARCHAR(16) NOT NULL,  -- like / dislike
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    document_id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    source_url VARCHAR(1024),
    doc_type VARCHAR(32),  -- policy / product / faq / manual
    dept_namespace VARCHAR(64),
    status VARCHAR(32) DEFAULT 'draft',  -- draft / active / rejected / failed / archived / deleted
    access_roles JSONB,
    content_hash VARCHAR(64),
    content TEXT,                        -- 文档正文(反馈候选审核入库时作为检索片段)
    source_session_id VARCHAR(64),       -- 来源会话(反馈候选追溯)
    ingest_error TEXT,                   -- 入库失败标记(worker 重试依据)
    search_vector tsvector,              -- PG 全文检索降级第三级
    reviewed_by VARCHAR(64) REFERENCES users(user_id),  -- 审核人
    reviewed_at TIMESTAMP,               -- 审核时间
    reject_reason TEXT,                  -- 拒绝原因
    uploaded_by VARCHAR(64) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,          -- prompt 逻辑名,如 planner_intent_classify
    version INTEGER NOT NULL,           -- 从 1 递增
    content TEXT NOT NULL,              -- 模板原文(含 {{ }} 转义)
    status VARCHAR(16) DEFAULT 'draft', -- draft / active / archived
    traffic_weight INTEGER DEFAULT 0,   -- A/B 分流权重 0-100(仅 active 版本有效)
    created_by VARCHAR(64) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP,
    UNIQUE (name, version)
);

-- Additive compatibility with supported legacy databases.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(64) REFERENCES users(user_id);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reject_reason TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ingest_error TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_session_id VARCHAR(64);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Additive compatibility with supported legacy databases.
ALTER TABLE users ADD COLUMN IF NOT EXISTS sso_issuer VARCHAR(512);
ALTER TABLE users ADD COLUMN IF NOT EXISTS sso_subject VARCHAR(255);

-- Preserve legacy credentials. Missing passwords need explicit operator repair.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE password_hash IS NULL OR btrim(password_hash) = '') THEN
        RAISE EXCEPTION USING ERRCODE = 'PBA01', MESSAGE = 'DB_LEGACY_PASSWORD_MISSING';
    END IF;
END;
$$;
ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_sso_identity
    ON users(sso_issuer, sso_subject)
    WHERE sso_issuer IS NOT NULL AND sso_subject IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_approvals_session_id ON approval_requests(session_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approvals_approver ON approval_requests(approver_id);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON user_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON user_memories(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_saga_session ON saga_transactions(session_id);
CREATE INDEX IF NOT EXISTS idx_saga_status ON saga_transactions(status);
CREATE INDEX IF NOT EXISTS idx_feedback_session ON user_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_documents_namespace ON documents(dept_namespace);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_search ON documents USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_documents_review_status
    ON documents (status) WHERE status IN ('draft', 'active', 'rejected');
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents (content_hash);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_name ON prompt_versions(name);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_status ON prompt_versions(status);
