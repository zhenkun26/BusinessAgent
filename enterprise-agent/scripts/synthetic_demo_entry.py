"""Private child entry for run_synthetic_demo.py; no inherited application configuration."""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = frozenset("""APP_ENV MODEL_PROFILE SYNTHETIC_DEMO_RUN_ID APP_HOST APP_PORT
WORKER_OBSERVATION_HOST WORKER_OBSERVATION_PORT POSTGRES_HOST POSTGRES_PORT POSTGRES_USER
POSTGRES_PASSWORD POSTGRES_DB REDIS_HOST REDIS_PORT REDIS_PASSWORD REDIS_DB JWT_SECRET_KEY
AUTH_REQUIRE_PASSWORD AUTH_CHECK_DB CORS_ALLOW_ORIGINS CHECKPOINT_BACKEND VECTOR_STORE_PROVIDER
EMBEDDING_PROVIDER RERANKER_PROVIDER TOOL_PROVIDER SSO_ENABLED TELEMETRY_MODE OTEL_ENABLED
MODEL_STARTUP_PROBES_ENABLED OBSERVABILITY_STORE_PATH BOOTSTRAP_ADMIN_ID BOOTSTRAP_ADMIN_USERNAME
BOOTSTRAP_ADMIN_PASSWORD""".split())

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("bootstrap", "api", "worker"))
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    if args.state.is_symlink():
        raise RuntimeError("DEMO_STATE_REJECTED")
    state = json.loads(args.state.read_text())
    env = state["environment"]
    if set(env) != ALLOWED or any(not isinstance(v, str) for v in env.values()):
        raise RuntimeError("DEMO_STATE_REJECTED")
    # Settings and telemetry imports occur only after inherited settings are removed.
    path = os.environ.get("PATH", "")
    os.environ.clear()
    os.environ.update(env)
    os.environ.update(PATH=path, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    # Resolve the installed native libpq before the runtime subprocess guard.
    # This imports the driver only; no connection or application settings are loaded.
    import psycopg  # noqa: F401
    from app.rag.synthetic_demo import install_process_guard, require_demo
    install_process_guard({int(env[k]) for k in (
        "APP_PORT", "WORKER_OBSERVATION_PORT", "POSTGRES_PORT", "REDIS_PORT")})
    # urllib3's import-time IPv6 bind is unrelated to this restricted demo.
    import socket
    ipv6 = socket.has_ipv6
    socket.has_ipv6 = False
    try:
        import urllib3
    finally:
        socket.has_ipv6 = ipv6
    from app.config import Settings, get_settings
    Settings.model_config["env_file"] = None
    settings = get_settings()
    require_demo(settings)
    if args.role == "bootstrap":
        from app.core.db_bootstrap import main as bootstrap
        if bootstrap(["apply", "--execute"]) or bootstrap(["admin", "--execute"]):
            raise RuntimeError("DEMO_BOOTSTRAP_FAILED")
        from app.graph.checkpointer import setup_postgres
        asyncio.run(setup_postgres())
    elif args.role == "worker":
        from app.worker import serve
        asyncio.run(serve())
    else:
        import uvicorn
        from app.main import app
        uvicorn.run(app, host=settings.app_host, port=settings.app_port,
                    loop="asyncio", access_log=False, log_level="warning",
                    timeout_graceful_shutdown=10)

if __name__ == "__main__":
    main()
