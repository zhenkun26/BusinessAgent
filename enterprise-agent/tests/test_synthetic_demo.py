"""Synthetic demo negative controls; no services, network, deletion or credentials."""
from __future__ import annotations
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_controls", ROOT / "app/rag/synthetic_demo.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

def settings(**changes):
    values = dict(app_env="dev", model_profile=d.PROFILE, synthetic_demo_run_id="a"*32,
        vector_store_provider="memory", embedding_provider="mock", reranker_provider="passthrough",
        tool_provider="mock", checkpoint_backend="postgres", postgres_host="127.0.0.1",
        redis_host="127.0.0.1", app_host="127.0.0.1", app_port=18763,
        worker_observation_host="127.0.0.1", worker_observation_port=18764,
        telemetry_mode="disabled", postgres_db="ba_demo_"+"a"*32, postgres_user="ba_demo",
        auth_require_password=True, auth_check_db=True, sso_enabled=False,
        model_startup_probes_enabled=False, jwt_secret_key="x"*48,
        postgres_password="y"*48, redis_password="z"*48, openai_api_key="",
        embedding_api_key="", reranker_api_key="", cohere_api_key="",
        crm_tool_provider="", mail_tool_provider="", ticket_tool_provider="")
    return SimpleNamespace(**{**values, **changes})

def test_demo_requires_explicit_profile_and_guard():
    assert not d.selected(settings(model_profile=""))
    assert d.configuration_errors(settings(model_profile="")) == []
    with patch.object(d, "_GUARDED", False):
        assert "DEMO_ENTRY_REQUIRED" in d.configuration_errors(settings())
    with patch.object(d, "_GUARDED", True):
        assert d.configuration_errors(settings()) == []

def test_demo_rejects_prod_and_nonlocal_or_real_resources():
    for update in (dict(app_env="prod"), dict(postgres_host="example.test"),
        dict(postgres_db="enterprise_agent"), dict(redis_host="localhost"),
        dict(app_host="0.0.0.0"), dict(worker_observation_host="0.0.0.0"),
        dict(vector_store_provider="milvus"), dict(embedding_provider="bailian"),
        dict(reranker_provider="local_bge"), dict(tool_provider="http"),
        dict(crm_tool_provider="http"), dict(sso_enabled=True),
        dict(model_startup_probes_enabled=True), dict(openai_api_key="not-a-real-key"),
        dict(auth_require_password=False), dict(auth_check_db=False)):
        assert "DEMO_CONFIGURATION_REJECTED" in d.configuration_errors(
            settings(**update), require_guard=False)

def test_guard_rejects_external_dns_ports_private_env_and_deletion():
    hooks = []
    with patch.object(d.sys, "addaudithook", side_effect=hooks.append), patch.object(d, "_GUARDED", False):
        d.install_process_guard({18763, 18764})
    guard = hooks[0]
    guard("socket.connect", (None, ("127.0.0.1", 18763)))
    for event, args in (
        ("socket.connect", (None, ("8.8.8.8", 443))),
        ("socket.connect", (None, ("127.0.0.1", 6379))),
        ("socket.getaddrinfo", ("example.test", 443)),
        ("open", ("/synthetic/.env", "r", 0)), ("os.remove", ("/synthetic/file",)),
        ("subprocess.Popen", ("/bin/sh", ["sh"]))):
        with pytest.raises(RuntimeError):
            guard(event, args)

def test_guard_rejects_invalid_port_sets():
    for ports in (set(), {80}, {True}, {70000}):
        with pytest.raises(ValueError):
            d.install_process_guard(ports)

async def request(method="GET", path="/health", body=b"", extra=None):
    output, calls = [], []
    async def app(scope, receive, send):
        calls.append(scope["path"])
        if scope["method"] == "POST":
            msg = await receive()
            assert msg["body"] == body
        await send(dict(type="http.response.start", status=200, headers=[]))
        await send(dict(type="http.response.body", body=b"real route"))
    with patch.object(d, "_GUARDED", True):
        boundary = d.DemoBoundary(app, settings=settings())
    headers = [(b"host", b"127.0.0.1:18763"), (b"content-type", b"application/json")]
    if extra:
        headers = [(k,v) for k,v in headers if k != extra[0]] + [extra]
    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return dict(type="http.request", body=body, more_body=False)
        return dict(type="http.disconnect")
    await boundary(dict(type="http", method=method, path=path, headers=headers), receive, async_append(output))
    return output, calls

def async_append(items):
    async def append(value):
        items.append(value)
    return append

def test_supported_greeting_delegates_to_real_route():
    for message in d.GREETINGS:
        result, calls = asyncio.run(request("POST", "/api/v1/chat/message",
                                            json.dumps({"message":message}).encode()))
        assert result[0]["status"] == 200 and calls == ["/api/v1/chat/message"]
        assert (b"x-businessagent-profile", d.PROFILE.encode()) in result[0]["headers"]

def test_unsupported_chat_cannot_reach_graph():
    for message in ("创建客户", "send email", "你好，查政策", "", ["你好"]):
        result, calls = asyncio.run(request("POST", "/api/v1/chat/stream",
                                            json.dumps({"message":message}).encode()))
        assert result[0]["status"] == 403 and calls == []

def test_admin_and_upload_routes_are_not_exposed():
    for method, path in (("POST","/api/v1/admin/documents"), ("POST","/api/v1/approval/x/resume"),
                         ("GET","/api/v1/auth/sso/login"), ("POST","/api/v1/prompts/test")):
        result, calls = asyncio.run(request(method, path, b"{}"))
        assert result[0]["status"] == 403 and calls == []

def test_host_and_origin_rebinding_are_rejected():
    for header in ((b"host", b"evil.example:18763"), (b"origin", b"https://evil.example")):
        result, calls = asyncio.run(request(extra=header))
        assert result[0]["status"] == 403 and calls == []

def test_request_size_and_content_type_are_bounded():
    result, calls = asyncio.run(request("POST","/api/v1/auth/login",b"x"*16385))
    assert result[0]["status"] == 413 and calls == []
    result, calls = asyncio.run(request("POST","/api/v1/auth/login",b"{}",
                                        (b"content-type", b"text/plain")))
    assert result[0]["status"] == 415 and calls == []

def test_demo_banner_and_offline_docs_are_explicit():
    for path in ("/demo","/docs"):
        result, calls = asyncio.run(request(path=path))
        assert result[0]["status"] == 200 and calls == []
        assert "演示".encode() in result[1]["body"]
        assert b"https://" not in result[1]["body"]

def test_history_keeps_real_authorization_path():
    result, calls = asyncio.run(request(path="/api/v1/chat/history/synthetic-other-user"))
    assert result[0]["status"] == 200 and calls == ["/api/v1/chat/history/synthetic-other-user"]

def test_disabled_model_refuses_every_invocation():
    model = d.disabled_model()
    with pytest.raises(RuntimeError, match="DEMO_MODEL_DISABLED"):
        model.invoke("synthetic")
    with pytest.raises(RuntimeError, match="DEMO_MODEL_DISABLED"):
        asyncio.run(model.ainvoke("synthetic"))


def test_guard_cannot_be_reinstalled():
    with patch.object(d, "_GUARDED", True):
        with pytest.raises(RuntimeError, match="DEMO_GUARD_ALREADY_INSTALLED"):
            d.install_process_guard({18763})

def test_entry_clears_inherited_environment_before_driver_and_app_import():
    source = (ROOT / "scripts/synthetic_demo_entry.py").read_text()
    assert source.index("os.environ.clear()") < source.index("import psycopg")
    assert source.index("import psycopg") < source.index("install_process_guard({")
    assert source.index("install_process_guard({") < source.index("from app.config import")
