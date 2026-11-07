-- Explicit bootstrap only. Preserve legacy saga_transactions and all evidence.
CREATE TABLE saga_runs (
    saga_id UUID PRIMARY KEY REFERENCES tool_executions(execution_id),
    context JSONB NOT NULL,
    plan_hash VARCHAR(64) NOT NULL,
    state VARCHAR(24) NOT NULL CHECK (state IN ('forward','aborting','succeeded','compensated','manual')),
    owner_token UUID,
    lease_until TIMESTAMPTZ,
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE saga_steps (
    saga_id UUID NOT NULL REFERENCES saga_runs(saga_id),
    slot INTEGER NOT NULL CHECK (slot >= 0),
    operation_id UUID NOT NULL UNIQUE REFERENCES tool_operations(operation_id),
    definition JSONB NOT NULL,
    result JSONB,
    compensation_id UUID NOT NULL UNIQUE,
    compensation_state VARCHAR(24) NOT NULL DEFAULT 'prepared'
        CHECK (compensation_state IN ('prepared','dispatched','committed','rejected','unknown')),
    compensation_request JSONB,
    compensation_receipt JSONB,
    PRIMARY KEY (saga_id, slot)
);
CREATE INDEX idx_saga_runs_recovery ON saga_runs(state, lease_until);
