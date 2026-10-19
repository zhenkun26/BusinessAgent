-- C21 additive identity; historical unkeyed rows remain unchanged.
ALTER TABLE audit_logs ADD COLUMN event_id UUID;
ALTER TABLE audit_logs ADD COLUMN occurred_at TIMESTAMPTZ;
ALTER TABLE audit_logs ADD COLUMN request_id VARCHAR(64);
ALTER TABLE audit_logs ADD COLUMN trace_id VARCHAR(32);
ALTER TABLE audit_logs ADD COLUMN task_id UUID;
CREATE UNIQUE INDEX idx_audit_event_id ON audit_logs(event_id);
CREATE INDEX idx_audit_request ON audit_logs(request_id);
CREATE INDEX idx_audit_task ON audit_logs(task_id);
ALTER TABLE task_jobs ADD COLUMN originating_request_id VARCHAR(64);
ALTER TABLE task_jobs ADD COLUMN originating_trace_id VARCHAR(32);
