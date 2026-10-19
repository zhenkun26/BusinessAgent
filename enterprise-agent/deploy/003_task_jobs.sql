-- Retained jobs; no automatic deletion, expiry cleanup or startup DDL.
CREATE TABLE task_jobs (
    task_id UUID PRIMARY KEY,
    queue_name VARCHAR(32) NOT NULL CHECK (queue_name IN ('tasks:doc_ingest', 'tasks:saga_retry')),
    scope_key VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    state VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'leased', 'running', 'done', 'dead')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 4),
    owner_token UUID,
    lease_until TIMESTAMPTZ,
    available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((state IN ('leased', 'running')) = (lease_until IS NOT NULL)),
    CHECK (state NOT IN ('leased', 'running') OR owner_token IS NOT NULL)
);
CREATE UNIQUE INDEX idx_task_jobs_scope ON task_jobs(scope_key);
CREATE INDEX idx_task_jobs_poll ON task_jobs(queue_name, state, available_at);
CREATE INDEX idx_task_jobs_expired ON task_jobs(queue_name, state, lease_until);
CREATE TABLE task_consumers (
    worker_id UUID NOT NULL,
    queue_name VARCHAR(32) NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (worker_id, queue_name)
);
