"""No-network negative controls for C10 subprocess configuration isolation."""
from __future__ import annotations
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("c10_entry", HERE / "run.py")
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)
root = entry.ROOT / "eval/results" / ("c10-entry-controls-" + uuid.uuid4().hex)
root.mkdir(parents=True)
empty = root / "empty"
empty.mkdir()
# This is an intentional synthetic trap, never a real user configuration.
(root / ".env").write_text("APP_ENV=prod\nMODEL_PROFILE=synthetic-demo-v1\nOTEL_ENABLED=true\n")
fixture = {"pg_host": "127.0.0.1", "pg_port": 1, "pg_user": "synthetic",
           "pg_password": "synthetic-not-a-secret", "c10_database": "c10_guard",
           "redis_host": "127.0.0.1", "redis_port": 2,
           "redis_password": "synthetic-not-a-secret"}
old = dict(os.environ)
try:
    os.environ.update(PYTHONOPTIMIZE="2", PYTHONPATH="untrusted",
                      OPENAI_API_KEY="synthetic-inherited",
                      MODEL_PROFILE="synthetic-demo-v1", OTEL_ENABLED="true",
                      OTEL_EXPORTER_OTLP_ENDPOINT="https://invalid.example",
                      LANGSMITH_API_KEY="synthetic-inherited")
    env = entry.environment(fixture, "postgres", empty)
finally:
    os.environ.clear()
    os.environ.update(old)
assert "PYTHONOPTIMIZE" not in env and env["PYTHONPATH"] == str(entry.ROOT)
assert "OPENAI_API_KEY" not in env and "LANGSMITH_API_KEY" not in env
assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env
assert env["MODEL_PROFILE"] == "" and env["OTEL_ENABLED"] == "false"
assert env["HOME"] == str(empty) and env["CHECKPOINT_TTL_DAYS"] == "7"

probe = r"""
import os,sys
from pathlib import Path
def guard(event,args):
    if event == "open" and isinstance(args[0], (str,bytes,os.PathLike)):
        if Path(os.fsdecode(args[0])).name == ".env":
            raise RuntimeError("SYNTHETIC_ENV_READ_TRAP")
    if event in {"socket.connect","socket.getaddrinfo","socket.bind","socket.sendto"}:
        raise RuntimeError("NETWORK_NOT_ALLOWED")
sys.addaudithook(guard)
from app.config import Settings
value=Settings()
assert value.app_env == "dev" and value.model_profile == ""
assert value.telemetry_mode == "disabled" and str(value.otel_enabled).lower() == "false"
assert value.openai_api_key == "" and value.checkpoint_backend == "postgres"
print("ISOLATED_SETTINGS_PASS")
"""
good = subprocess.run([sys.executable, "-B", "-c", probe], cwd=empty, env=env,
                      capture_output=True, text=True, timeout=30)
assert good.returncode == 0 and good.stdout.strip() == "ISOLATED_SETTINGS_PASS"
bad = subprocess.run([sys.executable, "-B", "-c", probe], cwd=root, env=env,
                     capture_output=True, text=True, timeout=30)
assert bad.returncode != 0 and "SYNTHETIC_ENV_READ_TRAP" in bad.stderr

tree = ast.parse((HERE / "run.py").read_text())
child = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "child")
calls = [n for n in ast.walk(child) if isinstance(n, ast.Call)
         and isinstance(n.func, ast.Name) and n.func.id == "invoke"]
assert calls and all(any(k.arg == "cwd" and isinstance(k.value, ast.Name)
                         and k.value.id == "output" for k in n.keywords) for n in calls)
for name in ("baseline.py", "faults.py"):
    tree = ast.parse((HERE / name).read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "Popen"]
    assert calls
    for call in calls:
        cwd = next(k.value for k in call.keywords if k.arg == "cwd")
        assert isinstance(cwd, ast.Subscript) and ast.literal_eval(cwd.slice) == "C10_EVIDENCE_DIR"
assert all(len(v) == len(set(v)) for v in entry.EXPECTED_CHECKS.values())
report = {"status": "PASS", "checks": 10,
          "scope": "synthetic dotenv trap, inherited configuration isolation and child cwd controls",
          "network": "not allowed", "fixture_data": "retained"}
(root / "report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report))
