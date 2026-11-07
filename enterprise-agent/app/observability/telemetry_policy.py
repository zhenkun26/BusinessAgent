"""Content-free telemetry admission; no third-party imports or configuration writes."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import os
import sys
from typing import Any, NoReturn
from urllib.parse import urlsplit


class TelemetryConfigurationError(RuntimeError):
    """Fixed rejection; never attach input, credentials or SDK exception bodies."""


@dataclass(frozen=True)
class TelemetryPolicy:
    mode: str
    enabled: bool
    endpoint: str


_PREFIXES = ('OTEL_', 'LANGCHAIN_', 'LANGSMITH_', 'TELEMETRY_')
_FALSE_ONLY = frozenset(
    prefix + suffix for prefix in ('LANGCHAIN_', 'LANGSMITH_')
    for suffix in ('TRACING', 'TRACING_V2', 'OTEL_ENABLED', 'OTEL_ONLY')
) | {'OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED'}
_EXPORTERS = frozenset({'OTEL_TRACES_EXPORTER', 'OTEL_METRICS_EXPORTER', 'OTEL_LOGS_EXPORTER'})
_OWNED = frozenset({'TELEMETRY_MODE', 'OTEL_ENABLED', 'OTEL_EXPORTER_OTLP_ENDPOINT',
                    'OTEL_SDK_DISABLED'})


def _reject(code: str = 'TELEMETRY_CONFIGURATION_REJECTED') -> NoReturn:
    raise TelemetryConfigurationError(code) from None


def _switch(value: object) -> bool:
    if type(value) is bool:
        return value
    if type(value) is str and value.strip().lower() in {'true', 'false'}:
        return value.strip().lower() == 'true'
    _reject()


def _collector(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        _reject()
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in {'http', 'https'} and parsed.hostname
                 and parsed.username is None and parsed.password is None
                 and not parsed.query and not parsed.fragment and parsed.path in {'', '/'}
                 and parsed.port is not None and 0 < parsed.port < 65536
                 and not any(c.isspace() or ord(c) < 32 for c in value))
        if parsed.scheme == 'http':
            valid = valid and parsed.hostname in {'localhost', '127.0.0.1', '::1', 'jaeger'}
    except (ValueError, TypeError):
        _reject()
    if not valid:
        _reject()
    return value


def validate_telemetry(values: Mapping[str, object]) -> TelemetryPolicy:
    """Validate process/effective Settings input without rendering opaque values."""
    config: dict[str, object] = {}
    for key, value in values.items():
        if type(key) is not str or not key.upper().startswith(_PREFIXES):
            continue
        key = key.upper()
        if type(value) not in (str, bool):
            _reject()
        if key in config and config[key] != value:
            _reject()
        config[key] = value
    mode = config.get('TELEMETRY_MODE', 'disabled')
    if type(mode) is not str or mode not in {'disabled', 'synthetic'}:
        _reject()
    enabled = _switch(config.get('OTEL_ENABLED', 'false'))
    for key, value in config.items():
        if key in _FALSE_ONLY:
            if _switch(value):
                _reject()
        elif key in _EXPORTERS:
            if type(value) is not str or value.strip().lower() != 'none':
                _reject()
        elif key not in _OWNED and value != '':
            # Dormant credentials/project names do not enable tracing.
            if key.startswith(('OTEL_', 'TELEMETRY_')) or any(
                    part in key for part in ('TRACING', 'OTEL', 'CALLBACK')):
                _reject()
    if 'OTEL_SDK_DISABLED' in config:
        disabled = _switch(config['OTEL_SDK_DISABLED'])
        if disabled == enabled:
            _reject()
    endpoint = config.get('OTEL_EXPORTER_OTLP_ENDPOINT', '')
    if enabled:
        if mode != 'synthetic':
            _reject()
        endpoint = _collector(endpoint)
    elif mode != 'disabled' or endpoint != '':
        _reject()
    return TelemetryPolicy(mode, enabled, endpoint or '')


def check_process_telemetry() -> TelemetryPolicy:
    """Run before dependency imports; instrumented launchers are unsupported."""
    if 'opentelemetry.instrumentation.auto_instrumentation' in sys.modules:
        _reject('TELEMETRY_BOOTSTRAP_REJECTED')
    return validate_telemetry(os.environ)


def validate_effective_telemetry(values: Mapping[str, object]) -> TelemetryPolicy:
    """Preserve SDK-only process options absent from declared Settings fields."""
    check_process_telemetry()
    effective = {key.upper(): value for key, value in os.environ.items()
                 if key.upper().startswith(_PREFIXES)}
    effective.update({key.upper(): value for key, value in values.items()
                      if type(key) is str and key.upper().startswith(_PREFIXES)})
    return validate_telemetry(effective)


def process_telemetry_signature() -> str:
    """Bind cached Settings to process telemetry with a non-exported digest."""
    values = sorted((key, value) for key, value in os.environ.items()
                    if key.upper().startswith(_PREFIXES))
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def admit_telemetry(settings: Any = None) -> TelemetryPolicy:
    """Recheck cached settings/environment before startup and factory side effects."""
    check_process_telemetry()
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    if getattr(settings, '_telemetry_process_signature', None) != process_telemetry_signature():
        _reject('TELEMETRY_CONFIGURATION_CHANGED')
    return validate_effective_telemetry({
        'TELEMETRY_MODE': settings.telemetry_mode,
        'OTEL_ENABLED': settings.otel_enabled,
        'OTEL_EXPORTER_OTLP_ENDPOINT': settings.otel_exporter_otlp_endpoint,
    })
