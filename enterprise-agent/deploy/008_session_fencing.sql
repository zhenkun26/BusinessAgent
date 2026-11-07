-- Additive C10 write ownership. Apply only after draining all older API writers.
CREATE TABLE session_write_fences (
    session_id VARCHAR(64) PRIMARY KEY REFERENCES sessions(session_id),
    owner_token UUID,
    lease_until TIMESTAMPTZ,
    CHECK ((owner_token IS NULL) = (lease_until IS NULL))
);

-- Accepted checkpoints are append-only; raw orphan runs are never published implicitly.
CREATE TABLE session_checkpoint_publications (
    publication_id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id),
    owner_token UUID NOT NULL,
    backend VARCHAR(16) NOT NULL CHECK (backend IN ('redis', 'postgres', 'memory')),
    thread_id VARCHAR(160) NOT NULL,
    checkpoint_ns TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (session_id, owner_token)
);
CREATE INDEX idx_session_checkpoint_history
    ON session_checkpoint_publications(session_id, publication_id DESC);
