-- C12 additive migration. Retain intents and receipts; no expiry or cleanup.
CREATE TABLE tool_executions (
    execution_id UUID PRIMARY KEY,
    scope_key VARCHAR(64) NOT NULL,
    plan_hash VARCHAR(64) NOT NULL,
    owner_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    calls JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tool_executions_scope ON tool_executions(scope_key);
CREATE TABLE tool_operations (
    operation_id UUID PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES tool_executions(execution_id),
    slot INTEGER NOT NULL CHECK (slot >= 0),
    intent JSONB NOT NULL,
    request JSONB,
    state VARCHAR(16) NOT NULL CHECK (state IN ('prepared','dispatched','unknown','committed','rejected')),
    receipt JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tool_operations_slot ON tool_operations(execution_id, slot);
