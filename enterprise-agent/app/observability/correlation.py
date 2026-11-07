"""Bounded server-owned correlation; IDs never become metric labels."""
from contextvars import ContextVar
import re
from typing import Any

request_id: ContextVar[str] = ContextVar('request_id', default='')
task_id: ContextVar[str] = ContextVar('task_id', default='')


def snapshot() -> dict[str, Any]:
    result = {'request_id': request_id.get() or None, 'task_id': task_id.get() or None,
              'trace_id': None}
    try:
        from opentelemetry import trace
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            result['trace_id'] = f'{context.trace_id:032x}'
    except (ImportError, AttributeError):
        pass
    for key, value in result.items():
        if value is not None and not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', value):
            result[key] = None
    return result
