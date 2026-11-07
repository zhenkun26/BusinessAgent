"""F2-05 synthetic startup/factory/configuration tests; no exporter or service execution."""
from __future__ import annotations

import ast
import asyncio
import builtins
import os
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.config import Settings, get_settings
from app.observability import telemetry_policy as policy

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'SYNTHETIC_DIAGNOSTIC_PERSON@example.invalid'
SYNTHETIC = {'TELEMETRY_MODE': 'synthetic', 'OTEL_ENABLED': 'true',
             'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://jaeger:4317'}


@pytest.fixture(autouse=True)
def clean_telemetry():
    with patch.dict(os.environ, {k: v for k, v in os.environ.items()
                               if not k.upper().startswith(policy._PREFIXES)}, clear=True):
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


def test_default_and_explicit_disable_are_admitted():
    assert policy.check_process_telemetry() == policy.TelemetryPolicy('disabled', False, '')
    value = {name: 'false' for name in policy._FALSE_ONLY}
    value.update({name: 'none' for name in policy._EXPORTERS})
    value['OTEL_SDK_DISABLED'] = 'true'
    assert not policy.validate_telemetry(value).enabled


@pytest.mark.parametrize('name', sorted(policy._FALSE_ONLY))
def test_each_unreviewed_enable_alias_is_rejected(name):
    with patch.dict(os.environ, {name: 'true', 'LANGCHAIN_TRACING_V2': 'false'}):
        # The V2 alias itself must be true for its own case.
        os.environ[name] = 'true'
        with pytest.raises(policy.TelemetryConfigurationError, match='^TELEMETRY_CONFIGURATION_REJECTED$'):
            policy.check_process_telemetry()


@pytest.mark.parametrize('value', ['', 'yes', '1', 'local', MARKER, None, 0])
def test_malformed_switch_does_not_fall_back(value):
    with pytest.raises(policy.TelemetryConfigurationError):
        policy.validate_telemetry({'LANGSMITH_TRACING': value})


@pytest.mark.parametrize('config', [
    {'OTEL_ENABLED': 'true'}, {'TELEMETRY_MODE': 'synthetic'},
    {'TELEMETRY_MODE': MARKER}, {**SYNTHETIC, 'OTEL_SDK_DISABLED': 'true'},
    {'OTEL_SDK_DISABLED': 'false'}, {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://jaeger:4317'},
    {'LANGSMITH_TRACING': 'false', 'langsmith_tracing': 'true'},
])
def test_incomplete_and_conflicting_configuration_is_rejected(config):
    with pytest.raises(policy.TelemetryConfigurationError):
        policy.validate_telemetry(config)


@pytest.mark.parametrize('name', [
    'OTEL_TRACES_EXPORTER', 'OTEL_METRICS_EXPORTER', 'OTEL_LOGS_EXPORTER',
    'OTEL_EXPORTER_OTLP_HEADERS', 'OTEL_EXPORTER_OTLP_TRACES_HEADERS',
    'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT', 'OTEL_PYTHON_DISTRO', 'OTEL_PYTHON_CONFIGURATOR',
    'OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST', 'OTEL_RESOURCE_ATTRIBUTES',
    'LANGSMITH_TRACING_MODE', 'LANGCHAIN_TRACING_MODE', 'LANGSMITH_CALLBACKS',
])
def test_unreviewed_export_capture_and_bootstrap_options_are_rejected(name):
    with pytest.raises(policy.TelemetryConfigurationError) as exc:
        policy.validate_telemetry({**SYNTHETIC, name: MARKER})
    assert MARKER not in str(exc.value)


@pytest.mark.parametrize('endpoint', [
    '', 'https://collector.example.invalid', 'http://collector.example.invalid:4317',
    'http://user:secret@jaeger:4317', 'http://jaeger:4317/path',
    'http://jaeger:4317?secret=' + MARKER, 'http://jaeger:4317#' + MARKER,
    'http://[::1', 'http://jaeger:65536', ' http://jaeger:4317',
    'http://jaeger:\n4317', 'file:///synthetic',
])
def test_collector_errors_are_fixed_without_endpoint_echo(endpoint):
    with pytest.raises(policy.TelemetryConfigurationError) as exc:
        policy.validate_telemetry({**SYNTHETIC, 'OTEL_EXPORTER_OTLP_ENDPOINT': endpoint})
    assert str(exc.value) == 'TELEMETRY_CONFIGURATION_REJECTED'


@pytest.mark.parametrize('endpoint', [
    'http://localhost:4317', 'http://127.0.0.1:4317', 'http://[::1]:4317',
    'http://jaeger:4317', 'https://collector.example.invalid:443',
])
def test_explicit_synthetic_collectors_are_parsed_without_calls(endpoint):
    value = policy.validate_telemetry({**SYNTHETIC, 'OTEL_EXPORTER_OTLP_ENDPOINT': endpoint})
    assert value.enabled and value.endpoint == endpoint


def test_preloaded_automatic_launcher_is_rejected():
    name = 'opentelemetry.instrumentation.auto_instrumentation'
    with patch.dict(sys.modules, {name: ModuleType(name)}):
        with pytest.raises(policy.TelemetryConfigurationError, match='TELEMETRY_BOOTSTRAP_REJECTED'):
            policy.check_process_telemetry()


def test_actual_settings_rejects_ignored_extra_sdk_options_without_pydantic_input_dump():
    with pytest.raises(policy.TelemetryConfigurationError) as exc:
        Settings(_env_file=None, LANGSMITH_TRACING='true', postgres_password=MARKER)
    assert str(exc.value) == 'TELEMETRY_CONFIGURATION_REJECTED'
    assert MARKER not in str(exc.value)


@pytest.mark.parametrize('key', ['otel_exporter_otlp_endpoint', 'telemetry_mode', 'otel_enabled'])
def test_invalid_owned_types_cannot_trigger_pydantic_sensitive_input_dump(key):
    with pytest.raises(policy.TelemetryConfigurationError) as exc:
        Settings(_env_file=None, postgres_password=MARKER, **{key: None})
    assert MARKER not in str(exc.value)


def test_actual_dotenv_source_cannot_hide_unreviewed_tracing(tmp_path):
    fixture = tmp_path / 'synthetic-telemetry-config.txt'
    fixture.write_text('LANGSMITH_TRACING=true\nPOSTGRES_PASSWORD=' + MARKER + '\n')
    with pytest.raises(policy.TelemetryConfigurationError) as exc:
        Settings(_env_file=fixture)
    assert MARKER not in str(exc.value)


def test_effective_synthetic_dotenv_is_admitted_without_environment_rewriting(tmp_path):
    fixture = tmp_path / 'synthetic-telemetry-config.txt'
    fixture.write_text('\n'.join(k + '=' + v for k, v in SYNTHETIC.items()))
    before = dict(os.environ)
    settings = Settings(_env_file=fixture)
    assert policy.admit_telemetry(settings).enabled
    assert dict(os.environ) == before


def test_sdk_only_process_option_cannot_disappear_in_effective_dotenv(tmp_path):
    fixture = tmp_path / 'synthetic-telemetry-config.txt'
    fixture.write_text('\n'.join(k + '=' + v for k, v in SYNTHETIC.items()))
    with patch.dict(os.environ, {'OTEL_SDK_DISABLED': 'true'}):
        with pytest.raises(policy.TelemetryConfigurationError):
            Settings(_env_file=fixture)


def test_false_constructor_alias_does_not_hide_enabled_process_alias():
    with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true'}):
        with pytest.raises(policy.TelemetryConfigurationError):
            Settings(_env_file=None, LANGSMITH_TRACING='false')


def test_cached_settings_reject_process_changes():
    settings = get_settings()
    assert not policy.admit_telemetry(settings).enabled
    with patch.dict(os.environ, {'LANGSMITH_PROJECT': 'synthetic-changed'}):
        with pytest.raises(policy.TelemetryConfigurationError, match='TELEMETRY_CONFIGURATION_CHANGED'):
            policy.admit_telemetry(settings)


def sdk_doubles():
    calls = SimpleNamespace(exporter=Mock(), processor=Mock(), provider=Mock(),
                            resource=Mock(), requests=Mock(), redis=Mock(), fastapi=Mock(),
                            trace=SimpleNamespace(set_tracer_provider=Mock(), get_tracer=Mock()))
    specifications = {
        'opentelemetry': {'trace': calls.trace},
        'opentelemetry.exporter.otlp.proto.grpc.trace_exporter': {'OTLPSpanExporter': calls.exporter},
        'opentelemetry.instrumentation.fastapi': {'FastAPIInstrumentor': calls.fastapi},
        'opentelemetry.instrumentation.redis': {'RedisInstrumentor': calls.redis},
        'opentelemetry.instrumentation.requests': {'RequestsInstrumentor': calls.requests},
        'opentelemetry.sdk.resources': {'Resource': calls.resource},
        'opentelemetry.sdk.trace': {'TracerProvider': calls.provider},
        'opentelemetry.sdk.trace.export': {'BatchSpanProcessor': calls.processor},
    }
    modules = {}
    for name, attributes in specifications.items():
        mod = ModuleType(name)
        mod.__dict__.update(attributes)
        modules[name] = mod
    return calls, modules


def tracing_source():
    return runpy.run_path(str(ROOT / 'app/observability/tracing.py'))


def test_disabled_actual_factories_construct_no_sdk_components():
    calls, modules = sdk_doubles()
    with patch.dict(sys.modules, modules):
        target = tracing_source()
        assert target['init_tracing']() is False
        assert target['instrument_fastapi'](object()) is None
    for name in ('exporter', 'processor', 'provider', 'resource', 'requests', 'redis', 'fastapi'):
        getattr(calls, name).assert_not_called()


def test_explicit_synthetic_actual_factories_preserve_c21_instrumentation():
    calls, modules = sdk_doubles()
    with patch.dict(os.environ, SYNTHETIC), patch.dict(sys.modules, modules):
        target = tracing_source()
        app = object()
        target['instrument_fastapi'](app)
        assert target['init_tracing']() is True
        assert target['init_tracing']() is True
    calls.fastapi.instrument_app.assert_called_once_with(app)
    calls.exporter.assert_called_once_with(endpoint='http://jaeger:4317', insecure=True, headers={})
    calls.requests.return_value.instrument.assert_called_once()
    calls.redis.return_value.instrument.assert_called_once()
    calls.resource.create.assert_not_called()


def test_https_factory_does_not_request_insecure_transport():
    calls, modules = sdk_doubles()
    with patch.dict(os.environ, {**SYNTHETIC,
            'OTEL_EXPORTER_OTLP_ENDPOINT': 'https://collector.example.invalid:443'}), \
            patch.dict(sys.modules, modules):
        target = tracing_source()
        assert target['init_tracing']() is True
    assert calls.exporter.call_args.kwargs['insecure'] is False


@pytest.mark.parametrize('failing', ['exporter', 'provider', 'requests', 'fastapi'])
def test_requested_sdk_failure_never_degrades_or_echoes(failing):
    calls, modules = sdk_doubles()
    logger = Mock()
    modules['loguru'] = ModuleType('loguru')
    modules['loguru'].logger = logger
    if failing == 'fastapi':
        calls.fastapi.instrument_app.side_effect = RuntimeError(MARKER)
    else:
        getattr(calls, failing).side_effect = RuntimeError(MARKER)
    with patch.dict(os.environ, SYNTHETIC), patch.dict(sys.modules, modules):
        target = tracing_source()
        with pytest.raises(policy.TelemetryConfigurationError) as exc:
            target['instrument_fastapi'](object()) if failing == 'fastapi' else target['init_tracing']()
    assert str(exc.value) == 'TELEMETRY_INITIALIZATION_FAILED'
    assert MARKER not in str(logger.mock_calls)


def test_missing_optional_sdk_is_a_fixed_failure_without_install_or_fallback():
    with patch.dict(os.environ, SYNTHETIC):
        target = tracing_source()
        original = builtins.__import__
        def missing(name, *args, **kwargs):
            if name == 'opentelemetry':
                raise ImportError(MARKER)
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=missing):
            with pytest.raises(policy.TelemetryConfigurationError) as exc:
                target['init_tracing']()
    assert str(exc.value) == 'TELEMETRY_INITIALIZATION_FAILED'


def test_partial_sdk_failure_closes_provider_and_latches_failure():
    calls, modules = sdk_doubles()
    calls.requests.side_effect = RuntimeError(MARKER)
    with patch.dict(os.environ, SYNTHETIC), patch.dict(sys.modules, modules):
        target = tracing_source()
        with pytest.raises(policy.TelemetryConfigurationError):
            target['init_tracing']()
        calls.requests.side_effect = None
        with pytest.raises(policy.TelemetryConfigurationError, match='TELEMETRY_INITIALIZATION_FAILED'):
            target['init_tracing']()
    calls.provider.return_value.shutdown.assert_called_once()
    calls.exporter.assert_called_once()


def test_failed_fastapi_registration_prevents_later_exporter_start():
    calls, modules = sdk_doubles()
    calls.fastapi.instrument_app.side_effect = RuntimeError(MARKER)
    with patch.dict(os.environ, SYNTHETIC), patch.dict(sys.modules, modules):
        target = tracing_source()
        with pytest.raises(policy.TelemetryConfigurationError):
            target['instrument_fastapi'](object())
        with pytest.raises(policy.TelemetryConfigurationError):
            target['init_tracing']()
    calls.exporter.assert_not_called()


def test_initialized_tracer_cannot_bypass_changed_environment():
    calls, modules = sdk_doubles()
    with patch.dict(os.environ, SYNTHETIC), patch.dict(sys.modules, modules):
        target = tracing_source()
        assert target['init_tracing']() is True
        with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true'}):
            with pytest.raises(policy.TelemetryConfigurationError):
                target['init_tracing']()
            with pytest.raises(policy.TelemetryConfigurationError):
                target['instrument_fastapi'](object())
    calls.exporter.assert_called_once()


def test_untrusted_service_name_is_rejected_before_exporter_construction():
    calls, modules = sdk_doubles()
    with patch.dict(os.environ, SYNTHETIC), patch.dict(sys.modules, modules):
        target = tracing_source()
        with pytest.raises(policy.TelemetryConfigurationError):
            target['init_tracing'](service_name=MARKER)
    calls.exporter.assert_not_called()


def test_package_bootstrap_rejects_before_sdk_imports():
    with patch.dict(os.environ, {'LANGSMITH_TRACING_V2': 'true'}):
        with pytest.raises(policy.TelemetryConfigurationError):
            exec(compile((ROOT / 'app/__init__.py').read_bytes(), 'synthetic_package', 'exec'), {})


@pytest.mark.parametrize('file', ['app/main.py', 'app/worker.py'])
def test_entry_rejects_before_business_dependency_import(file):
    # Execute the actual file with a recording import function: policy rejects first.
    imported = []
    original = builtins.__import__
    def recording(name, *args, **kwargs):
        imported.append(name)
        return original(name, *args, **kwargs)
    with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true'}), \
            patch('builtins.__import__', side_effect=recording):
        with pytest.raises(policy.TelemetryConfigurationError):
            exec(compile((ROOT / file).read_bytes(), file, 'exec'), {'__name__': 'synthetic_entry'})
    assert not any(n.startswith(('fastapi', 'app.api', 'app.core', 'app.tools')) for n in imported)


@pytest.mark.parametrize('file,function', [('app/main.py', 'lifespan'), ('app/worker.py', 'main')])
def test_startup_rechecks_before_model_or_database_work(file, function):
    tree = ast.parse((ROOT / file).read_text())
    node = next(n for n in tree.body if getattr(n, 'name', '') == function)
    node.decorator_list = []
    settings = Settings(_env_file=None)
    values = {'get_settings': lambda: settings, 'admit_telemetry': policy.admit_telemetry,
              'FastAPI': object}
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), values)
    with patch.dict(os.environ, {'LANGSMITH_TRACING': 'true'}):
        with pytest.raises(policy.TelemetryConfigurationError):
            asyncio.run(values[function](None).__anext__() if function == 'lifespan'
                        else values[function]())


@pytest.mark.parametrize('file,function', [('app/main.py', 'lifespan'), ('app/worker.py', 'main')])
def test_requested_sdk_failure_stops_before_model_probe_or_database(file, function):
    tree = ast.parse((ROOT / file).read_text())
    node = next(n for n in tree.body if getattr(n, 'name', '') == function)
    node.decorator_list = []
    settings = Settings(_env_file=None)
    model, database = AsyncMock(), AsyncMock()
    values = {'get_settings': lambda: settings, 'admit_telemetry': policy.admit_telemetry,
              'FastAPI': object, 'logger': Mock(), 'validate_production_settings': lambda _: [],
              'init_db': database, 'close_db': AsyncMock(), 'asyncio': asyncio}
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), values)
    modules = {}
    for name, attrs in {
        'app.rag.model_profile': {'verify_model_startup': model},
        'app.observability.audit': {'init_audit_logger': Mock()},
        'app.tools.base': {'init_all_tools': Mock()},
        'app.observability.tracing': {'init_tracing': Mock(side_effect=
            policy.TelemetryConfigurationError('TELEMETRY_INITIALIZATION_FAILED'))},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        modules[name] = module
    with patch.dict(sys.modules, modules):
        with pytest.raises(RuntimeError):
            asyncio.run(values[function](None).__anext__() if function == 'lifespan'
                        else values[function]())
    model.assert_not_awaited()
    database.assert_not_awaited()
