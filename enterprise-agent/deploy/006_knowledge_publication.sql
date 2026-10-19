-- Additive publication ledger; no historical visibility is inferred or data removed.
CREATE TABLE knowledge_publications (
    publication_id UUID PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id),
    input_hash VARCHAR(64) NOT NULL,
    source_hash VARCHAR(64) NOT NULL,
    snapshot JSONB NOT NULL,
    chunks JSONB NOT NULL,
    reviewer VARCHAR(64) REFERENCES users(user_id),
    state VARCHAR(16) NOT NULL DEFAULT 'staging' CHECK (state IN ('staging', 'published')),
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMPTZ,
    UNIQUE (document_id, input_hash)
);
ALTER TABLE documents ADD COLUMN active_publication UUID REFERENCES knowledge_publications(publication_id);
ALTER TABLE documents ADD COLUMN pending_publication UUID REFERENCES knowledge_publications(publication_id);
CREATE INDEX idx_publication_document ON knowledge_publications(document_id, created_at);
