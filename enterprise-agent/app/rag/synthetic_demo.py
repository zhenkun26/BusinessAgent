"""Dev-only no-model demo. No production, RAG or tool acceptance is implied."""
from __future__ import annotations
import json
import os
import re
import sys
from typing import Any

PROFILE = "synthetic-demo-v1"
GREETINGS = frozenset({"你好", "您好", "嗨", "hi"})
ANSWER = "合成演示：固定回复，没有模型调用。真实登录、JWT、会话、LangGraph和PostgreSQL参与了此流程；RAG、业务工具和生产验收不在本演示范围。"
_GUARDED = False

def selected(settings: Any) -> bool:
    return getattr(settings, "model_profile", "") == PROFILE

def configuration_errors(s: Any, *, require_guard: bool = True) -> list[str]:
    if not selected(s):
        return []
    expected = dict(app_env="dev", vector_store_provider="memory", embedding_provider="mock",
        reranker_provider="passthrough", tool_provider="mock", checkpoint_backend="postgres",
        postgres_host="127.0.0.1", redis_host="127.0.0.1", app_host="127.0.0.1",
        worker_observation_host="127.0.0.1", telemetry_mode="disabled")
    errors = []
    run = getattr(s, "synthetic_demo_run_id", "")
    if (any(getattr(s, k, None) != v for k, v in expected.items())
        or not re.fullmatch(r"[a-f0-9]{32}", run)
        or s.postgres_db != "ba_demo_" + run or s.postgres_user != "ba_demo"
        or not s.auth_require_password or not s.auth_check_db or s.sso_enabled
        or s.model_startup_probes_enabled
        or any(getattr(s, k, "") for k in ("openai_api_key", "embedding_api_key",
                                          "reranker_api_key", "cohere_api_key"))
        or any(getattr(s, k, "") not in ("", "mock") for k in
               ("crm_tool_provider", "mail_tool_provider", "ticket_tool_provider"))
        or len(s.jwt_secret_key) < 32 or len(s.postgres_password) < 24
        or len(s.redis_password) < 24):
        errors.append("DEMO_CONFIGURATION_REJECTED")
    if require_guard and not _GUARDED:
        errors.append("DEMO_ENTRY_REQUIRED")
    return errors

def require_demo(settings: Any) -> None:
    if not selected(settings) or configuration_errors(settings):
        raise RuntimeError("DEMO_CONFIGURATION_REJECTED")

def install_process_guard(ports: set[int]) -> None:
    """Python-process guard only; not a claim about browser/global network isolation."""
    global _GUARDED
    if _GUARDED:
        raise RuntimeError("DEMO_GUARD_ALREADY_INSTALLED")
    if not ports or any(type(p) is not int or not 1024 <= p <= 65535 for p in ports):
        raise ValueError("DEMO_PORTS_REJECTED")
    def guard(event: str, args: tuple) -> None:
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            from pathlib import Path
            if Path(os.fsdecode(args[0])).name.startswith(".env"):
                raise RuntimeError("DEMO_PRIVATE_ENV_DENIED")
        if event in {"socket.connect", "socket.bind", "socket.sendto"}:
            addr = args[-1]
            if not isinstance(addr, tuple) or len(addr) != 2 or addr[0] != "127.0.0.1" or addr[1] not in ports:
                raise RuntimeError("DEMO_EGRESS_DENIED")
        if event == "socket.getaddrinfo" and (args[0] != "127.0.0.1" or int(args[1]) not in ports):
            raise RuntimeError("DEMO_DNS_DENIED")
        if event in {"os.remove", "os.rmdir", "os.rename", "os.system", "subprocess.Popen"}:
            raise RuntimeError("DEMO_PROCESS_MUTATION_DENIED")
    sys.addaudithook(guard)
    _GUARDED = True

def disabled_model() -> Any:
    from langchain_core.language_models import BaseChatModel
    class NoModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "synthetic-demo-disabled"
        def _generate(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("DEMO_MODEL_DISABLED")
        async def _agenerate(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("DEMO_MODEL_DISABLED")
    return NoModel()

class DemoBoundary:
    """Allowlist around real auth/session routes, never an auth replacement."""
    CSP = b"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'"
    def __init__(self, app: Any, *, settings: Any) -> None:
        require_demo(settings)
        self.app = app
        self.authority = "127.0.0.1:" + str(settings.app_port)

    async def reply(self, send: Any, status: int, value: Any, *, html: bool = False) -> None:
        body = value.encode() if html else json.dumps(value, ensure_ascii=False).encode()
        headers = [(b"content-type", b"text/html; charset=utf-8" if html else b"application/json"),
            (b"content-length", str(len(body)).encode()), (b"cache-control", b"no-store"),
            (b"x-businessagent-profile", PROFILE.encode()), (b"content-security-policy", self.CSP)]
        await send(dict(type="http.response.start", status=status, headers=headers))
        await send(dict(type="http.response.body", body=body))

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            return
        rows = scope.get("headers", [])
        if len({k.lower() for k, _ in rows}) != len(rows):
            return await self.reply(send, 400, {"detail": "DEMO_DUPLICATE_HEADERS"})
        headers = dict(scope.get("headers", []))
        if (headers.get(b"host", b"").decode() != self.authority
            or headers.get(b"origin", b"").decode() not in ("", "http://" + self.authority)):
            return await self.reply(send, 403, {"detail": "DEMO_ORIGIN_REJECTED"})
        path, method = scope["path"], scope["method"]
        if method == "GET" and path in ("/", "/demo"):
            return await self.reply(send, 200, '<!doctype html><html lang="zh"><meta charset="utf-8"><title>Synthetic demo</title><body style="margin:0"><div style="padding:16px;background:#fff1ba;font:16px sans-serif"><b>synthetic-demo-v1 · 仅本机合成演示</b>：仅登录、输入“你好”和查看本人历史；没有模型、RAG、业务工具或生产验收。<a href="/docs">API说明</a></div><iframe title="实际应用UI" src="/ui/" style="width:100%;height:85vh;border:0"></iframe></body></html>', html=True)
        if method == "GET" and path in ("/ui", "/ui/", "/ui/index.html"):
            from pathlib import Path
            source = (Path(__file__).resolve().parents[1] / "static/index.html").read_text()
            banner = '<div role="note" style="position:fixed;top:0;left:0;right:0;z-index:99999;background:#fff1ba;color:#111;padding:8px;text-align:center">synthetic-demo-v1 · 合成演示：仅“你好”与本人历史；无模型、RAG、工具或生产验收</div>'
            source = source.replace("<body>", '<body data-businessagent-profile="synthetic-demo-v1" style="padding-top:40px">' + banner, 1)
            return await self.reply(send, 200, source, html=True)
        if method == "GET" and path in ("/docs", "/redoc"):
            return await self.reply(send, 200, '<html><meta charset="utf-8"><h1>合成演示 API</h1><p>不加载外部脚本。<a href="/openapi.json">实际应用 OpenAPI JSON</a></p><p>真实登录、身份、固定问候、本人历史。其他操作拒绝，生产与RAG未验收。</p></html>', html=True)
        read_ok = path in ("/health", "/ready", "/openapi.json", "/api/v1/auth/me") or path.startswith(("/ui/", "/api/v1/chat/history/"))
        post_ok = path in ("/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/chat/message", "/api/v1/chat/stream", "/api/v1/chat/cancel")
        if not ((method == "GET" and read_ok) or (method == "POST" and post_ok)):
            return await self.reply(send, 403, {"detail": "DEMO_UNSUPPORTED_OPERATION"})
        if method == "POST":
            if headers.get(b"content-type", b"").split(b";")[0] != b"application/json":
                return await self.reply(send, 415, {"detail": "DEMO_JSON_REQUIRED"})
            body = b""
            while True:
                msg = await receive()
                if msg["type"] != "http.request":
                    return
                body += msg.get("body", b"")
                if len(body) > 16384:
                    return await self.reply(send, 413, {"detail": "DEMO_REQUEST_TOO_LARGE"})
                if not msg.get("more_body"):
                    break
            if path in ("/api/v1/chat/message", "/api/v1/chat/stream"):
                try:
                    value = json.loads(body)
                    valid = isinstance(value, dict) and value.get("message") in GREETINGS
                except (ValueError, TypeError):
                    valid = False
                if not valid:
                    return await self.reply(send, 403, {"detail": "DEMO_UNSUPPORTED_OPERATION"})
            sent = False
            original_receive = receive
            async def replay() -> dict:
                nonlocal sent
                if not sent:
                    sent = True
                    return dict(type="http.request", body=body, more_body=False)
                return await original_receive()
            receive = replay
        async def labeled(msg: dict) -> None:
            if msg["type"] == "http.response.start":
                msg = {**msg, "headers": [*msg.get("headers", []),
                    (b"x-businessagent-profile", PROFILE.encode()),
                    (b"content-security-policy", self.CSP)]}
            await send(msg)
        await self.app(scope, receive, labeled)
