"""Plan or execute synthetic-only acceptance against a retained starter-owned demo."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import sys
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def require(value: bool) -> None:
    if not value:
        raise RuntimeError("DEMO_ACCEPTANCE_CHECK_FAILED")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("DEMO_ACCEPTANCE_REDIRECT_REJECTED")


def execute(run: Path, require_python: bool, report: dict) -> None:
    require(not any(p.is_symlink() for p in (run, *run.parents)))
    state_path = run / "private-state.json"
    receipt_path = run / "receipt.json"
    require(not state_path.is_symlink() and not receipt_path.is_symlink())
    require(state_path.stat().st_mode & 0o077 == 0)
    state = json.loads(state_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    e = state["environment"]
    ident = state["run_id"]
    require(bool(re.fullmatch("[a-f0-9]{32}", ident)))
    require(receipt["run_id"] == ident == e["SYNTHETIC_DEMO_RUN_ID"])
    require(receipt["status"] == "READY_SYNTHETIC_ONLY")
    require(receipt["profile"] == e["MODEL_PROFILE"] == "synthetic-demo-v1")
    require(receipt["run_directory"] == str(run))
    require(e["APP_ENV"] == "dev" and e["POSTGRES_USER"] == "ba_demo")
    require(e["POSTGRES_DB"] == "ba_demo_" + ident)
    require(all(e[k] == "127.0.0.1" for k in
        ("APP_HOST", "POSTGRES_HOST", "REDIS_HOST", "WORKER_OBSERVATION_HOST")))
    ports = {int(e[k]) for k in
        ("APP_PORT", "POSTGRES_PORT", "REDIS_PORT", "WORKER_OBSERVATION_PORT")}
    require(len(ports) == 4 and all(1024 <= p <= 65535 for p in ports))
    url = "http://127.0.0.1:" + e["APP_PORT"]
    require(receipt["url"] == url + "/demo")
    spec = importlib.util.spec_from_file_location("demo_launcher", ROOT / "scripts/run_synthetic_demo.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    require(receipt["containers"] == ["ba-demo-" + ident + "-pg", "ba-demo-" + ident + "-redis"])
    for name, kind, port in zip(receipt["containers"], ("pg", "redis"), ("5432/tcp", "6379/tcp")):
        info = json.loads(launcher.docker_call(["inspect", name]))[0]
        require(info["Config"]["Labels"]["businessagent.synthetic-demo"] == ident)
        require(info["State"]["Running"] is True)
        require(info["Config"]["Image"] == launcher.IMAGES[kind])
        binding = info["NetworkSettings"]["Ports"][port]
        expected_port = e["POSTGRES_PORT" if kind == "pg" else "REDIS_PORT"]
        require(binding == [{"HostIp": "127.0.0.1", "HostPort": expected_port}])

    # No app settings or inherited provider credentials are used.
    os.environ.clear()
    import bcrypt
    import psycopg
    report["driver"] = {"scope": "acceptance process; app environment must separately exclude binary/C wrappers",
                        "implementation": psycopg.pq.__impl__,
                        "libpq_version": psycopg.pq.version()}
    if require_python:
        require(psycopg.pq.__impl__ == "python")
    spec = importlib.util.spec_from_file_location("demo_boundary", ROOT / "app/rag/synthetic_demo.py")
    boundary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boundary)
    boundary.install_process_guard(ports)
    files = sorted(set((ROOT / "app").rglob("*.py")) |
                   set((ROOT / "scripts").glob("*synthetic_demo*.py")) |
                   {p for p in (ROOT / "app/static").rglob("*") if p.is_file()})
    report["source_binding_scope"] = "Current on-disk application, UI and demo scripts; startup identity is verified separately."
    report["source_sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(name, path, body=None, token=None, expected=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url + path,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with opener.open(req, timeout=60) as response:
                code, raw = response.status, response.read(2_000_000).decode()
        except urllib.error.HTTPError as response:
            code, raw = response.code, response.read(2_000_000).decode()
        report["checks"].append({"name": name, "status": code, "expected": expected,
                                 "pass": code == expected})
        require(code == expected)
        try:
            return json.loads(raw)
        except ValueError:
            return raw

    call("health", "/health")
    call("ready", "/ready")
    require("synthetic-demo-v1" in call("ui", "/ui/"))
    call("bad_password", "/api/v1/auth/login",
         {"username": e["BOOTSTRAP_ADMIN_USERNAME"], "password": "wrong"}, expected=401)
    token = call("login", "/api/v1/auth/login",
        {"username": e["BOOTSTRAP_ADMIN_USERNAME"],
         "password": e["BOOTSTRAP_ADMIN_PASSWORD"]})["access_token"]
    call("me", "/api/v1/auth/me", token=token)
    answer = call("greeting", "/api/v1/chat/message", {"message": "你好"}, token)
    require(answer["checkpointer_backend"] == "postgres" and "合成演示" in answer["answer"])
    sid = answer["session_id"]
    require(bool(re.fullmatch("[a-zA-Z0-9_-]{1,128}", sid)))
    require(call("own_history", "/api/v1/chat/history/" + sid, token=token)["found"] is True)
    call("unsupported", "/api/v1/chat/message", {"message": "send real mail"}, token, 403)
    call("admin_block", "/api/v1/admin/users", token=token, expected=403)
    second = "synthetic_" + uuid.uuid4().hex
    password = secrets.token_hex(24)
    with psycopg.connect(host="127.0.0.1", port=int(e["POSTGRES_PORT"]),
            dbname=e["POSTGRES_DB"], user="ba_demo", password=e["POSTGRES_PASSWORD"],
            connect_timeout=10) as conn:
        conn.execute("INSERT INTO users (user_id,username,role,department,password_hash,is_active) "
            "VALUES (%s,%s,%s,%s,%s,%s)", (second, second, "salesperson", "sales",
            bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), True))
    other = call("login_second", "/api/v1/auth/login",
                 {"username": second, "password": password})["access_token"]
    call("cross_user_history", "/api/v1/chat/history/" + sid, token=other, expected=404)
    call("cross_user_cancel", "/api/v1/chat/cancel", {"session_id": sid}, other, 404)
    stream = call("stream", "/api/v1/chat/stream", {"message": "hi"}, token)
    require("data:" in stream and "合成演示" in stream)
    call("cancel_completed", "/api/v1/chat/cancel", {"session_id": sid}, token)
    report["status"] = "PASS"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--require-python-driver", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "PLAN", "scope": "15 synthetic local HTTP and DB checks",
            "requires": "starter-owned ready run; native libpq for --require-python-driver",
            "writes": "new synthetic user/session and redacted acceptance report; no deletion",
            "rag_accepted": False}))
        return 0
    if args.run_dir is None:
        parser.error("--run-dir is required with --execute")
    run = args.run_dir.absolute()
    report = {"status": "FAIL", "checks": [], "rag_accepted": False}
    try:
        execute(run, args.require_python_driver, report)
    except Exception:
        # Never include exceptions, response bodies, credentials or JWTs in public artifacts.
        report["error"] = "DEMO_ACCEPTANCE_FAILED"
    output = run / ("acceptance-" + uuid.uuid4().hex + ".json")
    if not any(p.is_symlink() for p in (run, *run.parents)) and run.is_dir():
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            json.dump(report, f, indent=2)
    print(json.dumps({"status": report["status"], "checks": len(report["checks"]),
                      "report": str(output)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
