-- Explicit migration only. Historical approval outcomes are not re-certified.
ALTER TABLE approval_requests ADD COLUMN execution_id UUID REFERENCES tool_executions(execution_id);
ALTER TABLE approval_requests ADD COLUMN execution_claim UUID;
ALTER TABLE approval_requests ADD COLUMN execution_deadline TIMESTAMPTZ;
ALTER TABLE approval_requests ADD COLUMN execution_error VARCHAR(64);
ALTER TABLE approval_requests ADD COLUMN execution_checked_at TIMESTAMPTZ;
CREATE UNIQUE INDEX idx_approval_execution ON approval_requests(execution_id)
    WHERE execution_id IS NOT NULL;
CREATE INDEX idx_approval_reconcile ON approval_requests(status, execution_deadline);
