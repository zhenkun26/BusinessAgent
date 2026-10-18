"""Admin-only callers expose bounded reference configuration and correlation metadata."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.tool_operations import fingerprint, valid_uuid
from app.tools.reference import PROFILE, SERVICES, resource_id


def configuration(settings: Any, get_tool: Any) -> dict[str, Any]:
    try:
        run_id = valid_uuid(settings.tool_reference_run_id)
        principal = resource_id(settings.tool_reference_principal)
    except Exception:
        run_id = principal = None
    services = {}
    tokens = []
    for service in ('crm', 'ticket', 'mail'):
        token = getattr(settings, service + '_api_token', '')
        tokens.append(token)
        services[service] = {
            'isolated_endpoint': getattr(settings, service + '_api_base', '').rstrip('/') ==
                f'http://reference-{service}:8080/api/v1',
            'credential_present': bool(token),
        }
    providers = {}
    for name in SERVICES:
        tool = get_tool(name)
        providers[name] = tool is not None and tool._effective_provider() == 'http'
    configured = (settings.tool_reference_profile == PROFILE and run_id is not None
                  and settings.auth_require_password and settings.auth_check_db
                  and len(set(tokens)) == 3 and all(tokens)
                  and all(all(state.values()) for state in services.values()) and all(providers.values()))
    return {'status': 'CONFIGURED' if configured else 'BLOCKED',
            'profile': PROFILE if settings.tool_reference_profile == PROFILE else None,
            'run_id': run_id, 'principal': principal, 'services': services,
            'http_tools': providers, 'runtime_acceptance': 'BLOCKED'}


async def collect(db: Any, session_id: str) -> dict[str, Any]:
    resource_id(session_id)
    queries = {
        'operations': '''SELECT o.operation_id,o.execution_id,o.state,o.request,
            o.intent->>'tool' AS tool,o.intent->'target'->>'service' AS service,
            o.intent->'target'->>'run_id' AS run_id FROM tool_operations o
            JOIN tool_executions e USING(execution_id) WHERE e.session_id=:sid
            ORDER BY o.execution_id,o.slot LIMIT 201''',
        'approvals': '''SELECT approval_id,session_id,requester_id,approver_id,status,
            operation_type FROM approval_requests WHERE session_id=:sid
            ORDER BY approval_id LIMIT 201''',
        'sagas': '''SELECT s.saga_id,s.state,s.error_code FROM saga_runs s
            JOIN tool_executions e ON e.execution_id=s.saga_id WHERE e.session_id=:sid
            ORDER BY s.saga_id LIMIT 201''',
        'steps': '''SELECT s.saga_id,s.operation_id,s.compensation_id,s.compensation_state
            FROM saga_steps s JOIN tool_executions e ON e.execution_id=s.saga_id
            WHERE e.session_id=:sid ORDER BY s.saga_id,s.slot LIMIT 201''',
        'jobs': '''SELECT j.task_id,j.state,j.error_code FROM task_jobs j
            JOIN tool_executions e ON j.scope_key='saga:' || e.execution_id::text
            WHERE e.session_id=:sid ORDER BY j.task_id LIMIT 201''',
        'audit': '''SELECT id,event_type,tool_name,success FROM audit_logs
            WHERE session_id=:sid ORDER BY id LIMIT 201''',
    }
    output: dict[str, Any] = {'session_id': session_id, 'snapshot_atomic': False}
    for name, sql in queries.items():
        rows = (await db.execute(text(sql), {'sid': session_id})).mappings().all()
        if len(rows) > 200:
            raise ValueError('REFERENCE_EVIDENCE_LIMIT')
        cleaned = []
        for item in rows:
            row = dict(item)
            if name == 'operations':
                request = row.pop('request')
                row['request_hash'] = fingerprint(request) if request is not None else None
            cleaned.append({key: str(value) if key.endswith('_id') and value is not None else value
                            for key, value in row.items()})
        output[name] = cleaned
    # Missing audit rows are not repaired here; recovery remains C21.
    return output
