"""Start/stop a retained, loopback-only real-app synthetic demo. Never installs dependencies."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/synthetic_demo_entry.py"
IMAGES = {
    "pg": "postgres@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab",
    "redis": "redis@sha256:c5d34a98396a4775e223c74e929162c35c5a2182901ba26b50ade939941ce14b",
}

def write_json(path: Path, value: dict, *, exclusive: bool = True) -> None:
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    with os.fdopen(os.open(path, flags, 0o600), "w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")

def docker() -> tuple[str, dict]:
    path = shutil.which("docker")
    if not path:
        candidate = Path.home() / ".docker/bin/docker"
        if candidate.is_file():
            path = str(candidate)
    if not path:
        raise RuntimeError("DEMO_DOCKER_REQUIRED")
    env = dict(os.environ)
    env["PATH"] = str(Path(path).resolve().parent) + os.pathsep + env.get("PATH", "")
    return path, env

def docker_call(args: list[str]) -> str:
    binary, env = docker()
    result = subprocess.run([binary, *args], env=env, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError("DEMO_DOCKER_COMMAND_FAILED")
    return result.stdout.strip()

def free_ports() -> list[int]:
    sockets = []
    try:
        for _ in range(4):
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            sockets.append(s)
        return [s.getsockname()[1] for s in sockets]
    finally:
        for s in sockets:
            s.close()

def stop(run: Path) -> None:
    state = json.loads((run / "private-state.json").read_text())
    receipt = json.loads((run / "receipt.json").read_text())
    ident = state["run_id"]
    if run.is_symlink() or len(ident) != 32 or receipt["run_id"] != ident:
        raise RuntimeError("DEMO_STATE_REJECTED")
    signaled = []
    for pid in receipt.get("pids", []):
        row = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                             capture_output=True, text=True, check=False)
        if row.returncode == 0 and str(ENTRY) in row.stdout and str(run / "private-state.json") in row.stdout:
            os.kill(pid, signal.SIGTERM)
            signaled.append(pid)
    for pid in signaled:
        for _ in range(100):
            row = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
            if row.returncode != 0 or row.stdout.strip().startswith("Z"):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("DEMO_PROCESS_STOP_TIMEOUT")
    for name in receipt.get("containers", []):
        binary, environment = docker()
        inspected = subprocess.run([binary, "inspect", name], env=environment,
                                   capture_output=True, text=True, timeout=30)
        if inspected.returncode:
            missing = {f"Error response from daemon: No such object: {name}",
                       f"Error response from daemon: No such container: {name}"}
            if (inspected.returncode == 1 and inspected.stderr.strip() in missing
                    and inspected.stdout.strip() in ("", "[]")):
                continue
            raise RuntimeError("DEMO_CONTAINER_INSPECT_FAILED")
        info = json.loads(inspected.stdout)[0]
        if info["Config"]["Labels"].get("businessagent.synthetic-demo") != ident:
            raise RuntimeError("DEMO_CONTAINER_OWNERSHIP_REJECTED")
        if info["State"]["Running"]:
            docker_call(["stop", "--time", "15", name])
    write_json(run / ("stop-" + uuid.uuid4().hex + ".json"),
               {"run_id": ident, "status": "STOPPED_RETAINED", "deleted": False})
    print("Stopped owned demo processes/containers. All evidence and data retained.")

def start(run: Path) -> None:
    if sys.version_info < (3, 11) or os.name != "posix":
        raise RuntimeError("DEMO_PYTHON311_POSIX_REQUIRED")
    # No private app configuration is imported in the launcher.
    check = subprocess.run([sys.executable, "-I", "-B", "-c",
        "import psycopg, fastapi, uvicorn, asyncpg, langgraph.checkpoint.postgres"],
        capture_output=True, text=True, timeout=30)
    if check.returncode:
        raise RuntimeError("DEMO_DEPENDENCIES_REQUIRED: install declared dependencies and libpq/approved psycopg binary support")
    docker_call(["info", "--format", "{{.ServerVersion}}"])
    run.mkdir(parents=True, exist_ok=False)
    ident = uuid.uuid4().hex
    pg, redis, api, worker = free_ports()
    secret = lambda: secrets.token_hex(24)
    env = {
        "APP_ENV": "dev", "MODEL_PROFILE": "synthetic-demo-v1", "SYNTHETIC_DEMO_RUN_ID": ident,
        "APP_HOST": "127.0.0.1", "APP_PORT": str(api), "WORKER_OBSERVATION_HOST": "127.0.0.1",
        "WORKER_OBSERVATION_PORT": str(worker), "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": str(pg),
        "POSTGRES_USER": "ba_demo", "POSTGRES_PASSWORD": secret(), "POSTGRES_DB": "ba_demo_" + ident,
        "REDIS_HOST": "127.0.0.1", "REDIS_PORT": str(redis), "REDIS_PASSWORD": secret(), "REDIS_DB": "0",
        "JWT_SECRET_KEY": secret(), "AUTH_REQUIRE_PASSWORD": "true", "AUTH_CHECK_DB": "true",
        "CORS_ALLOW_ORIGINS": "http://127.0.0.1:" + str(api), "CHECKPOINT_BACKEND": "postgres",
        "VECTOR_STORE_PROVIDER": "memory", "EMBEDDING_PROVIDER": "mock", "RERANKER_PROVIDER": "passthrough",
        "TOOL_PROVIDER": "mock", "SSO_ENABLED": "false", "TELEMETRY_MODE": "disabled", "OTEL_ENABLED": "false",
        "MODEL_STARTUP_PROBES_ENABLED": "false", "OBSERVABILITY_STORE_PATH": str(run / "audit.sqlite3"),
        "BOOTSTRAP_ADMIN_ID": "demo_" + ident[:12], "BOOTSTRAP_ADMIN_USERNAME": "Synthetic Demo",
        "BOOTSTRAP_ADMIN_PASSWORD": secret(),
    }
    state_file = run / "private-state.json"
    write_json(state_file, {"run_id": ident, "environment": env})
    receipt = {"run_id": ident, "profile": env["MODEL_PROFILE"], "status": "STARTING",
               "containers": [], "pids": [], "images": IMAGES, "url": "http://127.0.0.1:" + str(api) + "/demo",
               "run_directory": str(run), "no_external_models": True, "rag_accepted": False}
    write_json(run / "receipt.json", receipt)
    network = "ba-demo-" + ident
    receipt["network"] = network
    write_json(run / "receipt.json", receipt, exclusive=False)
    docker_call(["network", "create", "--label", "businessagent.synthetic-demo=" + ident, network])
    for service in ("pg", "redis"):
        name = network + "-" + service
        args = ["run", "-d", "--name", name, "--network", network,
                "--label", "businessagent.synthetic-demo=" + ident,
                "--memory", "512m" if service == "pg" else "192m", "--cpus", "1",
                "--pids-limit", "128", "-p", "127.0.0.1:" + str(pg if service == "pg" else redis)
                    + (":5432" if service == "pg" else ":6379")]
        if service == "pg":
            args += ["-e", "POSTGRES_USER=ba_demo", "-e", "POSTGRES_DB=" + env["POSTGRES_DB"],
                     "-e", "POSTGRES_PASSWORD=" + env["POSTGRES_PASSWORD"],
                     "-v", name + "-data:/var/lib/postgresql/data", IMAGES[service]]
        else:
            args += [IMAGES[service], "redis-server", "--requirepass", env["REDIS_PASSWORD"],
                     "--save", "", "--appendonly", "no"]
        receipt["containers"].append(name)
        write_json(run / "receipt.json", receipt, exclusive=False)
        docker_call(args)
    for _ in range(60):
        if subprocess.run([docker()[0], "exec", receipt["containers"][0], "pg_isready",
                           "-h", "127.0.0.1", "-U", "ba_demo", "-d", env["POSTGRES_DB"]],
                          env=docker()[1], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            try:
                with socket.create_connection(("127.0.0.1", pg), timeout=2):
                    pass
                break
            except OSError:
                pass
        time.sleep(1)
    else:
        raise RuntimeError("DEMO_DATABASE_START_TIMEOUT")
    with (run / "bootstrap.log").open("x") as log:
        result = subprocess.run([sys.executable, "-I", "-B", str(ENTRY), "bootstrap", "--state", str(state_file)],
                                cwd=run, stdout=log, stderr=log, timeout=120)
    if result.returncode:
        raise RuntimeError("DEMO_BOOTSTRAP_FAILED")
    for role in ("worker", "api"):
        with (run / (role + ".log")).open("x") as log:
            child = subprocess.Popen([sys.executable, "-I", "-B", str(ENTRY), role, "--state", str(state_file)],
                                     cwd=run, stdout=log, stderr=log, start_new_session=True)
        receipt["pids"].append(child.pid)
        write_json(run / "receipt.json", receipt, exclusive=False)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(90):
        try:
            with opener.open("http://127.0.0.1:" + str(api) + "/ready", timeout=2) as r:
                ready = json.load(r)
            if ready["status"] == "ready":
                break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    else:
        raise RuntimeError("DEMO_READINESS_TIMEOUT: retained logs and containers are not deleted")
    receipt["status"] = "READY_SYNTHETIC_ONLY"
    write_json(run / "receipt.json", receipt, exclusive=False)
    print(json.dumps({"url": receipt["url"], "username": env["BOOTSTRAP_ADMIN_USERNAME"],
                      "password": env["BOOTSTRAP_ADMIN_PASSWORD"], "run_directory": str(run),
                      "scope": "Synthetic greetings only; no model/RAG/tool/production acceptance."},
                     ensure_ascii=False))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "start", "stop"))
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        print(json.dumps({"profile": "synthetic-demo-v1", "requires": ["Python 3.11+ POSIX",
            "declared Python dependencies", "libpq or approved psycopg binary support", "Docker"],
            "images": IMAGES, "bind": "127.0.0.1 only", "deletes_data": False,
            "model_calls": 0, "supported": ["login", "synthetic greeting", "own history"]}))
        return 0
    if not args.execute or args.run_dir is None:
        parser.error("--execute and a fresh --run-dir are required (existing owned dir for stop)")
    run = args.run_dir.absolute()
    if any(p.is_symlink() for p in (run, *run.parents)):
        parser.error("symlink paths are not allowed")
    try:
        start(run) if args.command == "start" else stop(run)
        return 0
    except Exception as exc:
        # Fixed known errors only; never print config, passwords or raw service errors.
        message = str(exc)
        print(message if message.startswith("DEMO_") else "DEMO_FAILED: inspect retained local evidence", file=sys.stderr)
        if (run / "receipt.json").is_file():
            print("Retained run; stop only its owned services with:", file=sys.stderr)
            print(f"{sys.executable} -I -B {Path(__file__).resolve()} stop --execute --run-dir {run}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
