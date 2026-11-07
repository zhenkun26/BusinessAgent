"""Explicit synthetic C10 persistence slice; never full C10/RAG/UAT acceptance.

Requires Docker and the project's exact Python dependencies. Creates only uniquely
named, labelled containers/volumes; stops its own containers without deleting them.
Only report.json is safe for CI upload. Other retained files may contain fixture data.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT.parent
PG_IMAGE = "postgres@sha256:5983db9a9c6ad225a48a46cfe2e03e6680b1826662befd0465eb05b34cb1c64e"
REDIS_IMAGE = "redis/redis-stack-server@sha256:a8d64e9f5bc99dc83f2a807a93f44d59efab0d2c4f09cff03f01b8753842e0cc"
EXPECTED_CHECKS = {'C10-PG-BASE': ['worker_0_real_backend_ready',
                 'worker_1_real_backend_ready',
                 'independent_pids',
                 'active_overlap_refused',
                 'cross_session_thread_isolated',
                 'independent_session_published',
                 'expired_owner_cannot_renew',
                 'successor_new_thread_token',
                 'expired_owner_publish_rejected',
                 'stale_release_preserves_successor_redis_pg',
                 'successor_publication_commits',
                 'pointer_terminal_tokens_owner_consistent',
                 'duplicate_publish_rejected',
                 'late_raw_aput_and_aput_writes_do_not_publish',
                 'cross_process_exact_id_read',
                 'pending_writes_real_roundtrip',
                 'other_session_unchanged'],
 'C10-REDIS-BASE': ['worker_0_real_backend_ready',
                    'worker_1_real_backend_ready',
                    'independent_pids',
                    'active_overlap_refused',
                    'cross_session_thread_isolated',
                    'independent_session_published',
                    'expired_owner_cannot_renew',
                    'successor_new_thread_token',
                    'expired_owner_publish_rejected',
                    'stale_release_preserves_successor_redis_pg',
                    'successor_publication_commits',
                    'pointer_terminal_tokens_owner_consistent',
                    'duplicate_publish_rejected',
                    'late_raw_aput_and_aput_writes_do_not_publish',
                    'cross_process_exact_id_read',
                    'pending_writes_real_roundtrip',
                    'other_session_unchanged'],
 'C10-PG-FAULT': ['aput_paused_inside_real_saver',
                  'aput_successor_published_while_old_suspended',
                  'aput_late_real_write_completed',
                  'aput_stale_publish_rejected',
                  'aput_late_write_keeps_pointer_status_tokens',
                  'aput_successor_exact_checkpoint_readable',
                  'aput_orphan_is_real_persisted_data',
                  'aput_source_harness_stable',
                  'aput_writes_paused_inside_real_saver',
                  'aput_writes_successor_published_while_old_suspended',
                  'aput_writes_late_real_write_completed',
                  'aput_writes_stale_publish_rejected',
                  'aput_writes_late_write_keeps_pointer_status_tokens',
                  'aput_writes_successor_exact_checkpoint_readable',
                  'aput_writes_orphan_is_real_persisted_data',
                  'aput_writes_source_harness_stable',
                  'commit_response_actually_dropped_once',
                  'lost_commit_ack_returns_failure',
                  'lost_ack_commit_persisted_pointer_status_tokens',
                  'lost_ack_retry_cannot_republish',
                  'lost_ack_failure_callback_cannot_undo',
                  'lost_ack_no_duplicate_token_or_pointer',
                  'lost_ack_exact_checkpoint_readable',
                  'lost_ack_source_harness_stable'],
 'C10-PG-RESTART': ['fresh_reader_process',
                    'postgres_actually_restarted',
                    'postgres_version_unchanged',
                    'exact_ids_pending_writes_pointer_status_tokens_survived',
                    'source_harness_unchanged_across_restart']}
EXPECTED = {case: len(names) for case, names in EXPECTED_CHECKS.items()}
BLOCKED = [
    "FULL_GRAPH_PACKAGE_COMPATIBILITY", "REDIS_RETENTION_RESTART_ZERO_TTL",
    "INITIALIZATION_CANCELLATION_RESOURCE_BOUNDS", "PG_SETUP_INTERRUPTION",
    "REDIS_ONLY_EXPIRY", "PG_ONLY_EXPIRY", "ALL_LATE_CALLBACK_INTERLEAVINGS",
    "ROW_LOCK_COMMIT_TAKEOVER_INTERLEAVINGS", "ALL_OUTAGE_PUBLICATION_BOUNDARIES",
    "HISTORY_ORPHAN_EXACT_ID_BACKEND_MISMATCH", "API_JWT_SSE_BROWSER_CANCELLATION",
    "V7_DRIFT_REFUSAL_BACKUP_RESTORE", "FULL_RUNTIME_RAG", "FORMAL_UAT",
    "SOURCE_RIGHTS", "RELEASE_ACCEPTANCE",
]


def invoke(args, *, env=None, timeout=240, cwd=REPO):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout, check=True)


def binding():
    paths = invoke(["git", "ls-files", "-z"]).stdout.split("\0")
    hashes = {n: hashlib.sha256((REPO / n).read_bytes()).hexdigest()
              for n in paths if n}
    return {
        "commit": invoke(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "tree": invoke(["git", "rev-parse", "HEAD^{tree}"]).stdout.strip(),
        "clean": not invoke(["git", "-c", "core.fileMode=false", "status",
                             "--porcelain"]).stdout.strip(),
        "tracked_sources_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "schema_manifest_sha256": hashlib.sha256(
            (ROOT / "deploy/schema_manifest.json").read_bytes()).hexdigest(),
    }


def environment(config, backend, output):
    # Application children do not inherit provider credentials, profile or telemetry.
    safe_process_keys = ("PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL", "TZ")
    env = {key: os.environ[key] for key in safe_process_keys if key in os.environ}
    env["HOME"] = str(output)
    env.update(PYTHON_DOTENV_DISABLED="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT), CHECKPOINT_BACKEND=backend, CHECKPOINT_TTL_DAYS="7",
               APP_ENV="dev", MODEL_PROFILE="",
               TELEMETRY_MODE="disabled", OTEL_ENABLED="false",
               C10_ISOLATED_FIXTURE="confirmed", C10_CONFIG_PATH=str(output / "connections.json"),
               C10_EVIDENCE_DIR=str(output))
    for key in ("host", "port", "user", "password"):
        env["POSTGRES_" + key.upper()] = str(config["pg_" + key])
    env["POSTGRES_DB"] = config["c10_database"]
    for key in ("host", "port", "password"):
        env["REDIS_" + key.upper()] = str(config["redis_" + key])
    env["REDIS_DB"] = "0"
    return env


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "--execute":
        print("Explicit --execute creates isolated synthetic fixtures; no deletion or deployment.")
        return 2
    run_id = uuid.uuid4().hex
    output = ROOT / "eval/results" / ("c10-persistence-" + run_id)
    output.mkdir(parents=True)
    report = {"schema": "c10-persistence-v1", "run_id": run_id, "platform": sys.platform,
              "required_cases": EXPECTED, "cases": {}, "blocked_requirements": BLOCKED,
              "full_c10_acceptance": False, "full_rag": "BLOCKED", "uat": "BLOCKED",
              "phase_execution": "FAIL", "release_allowed": False, "containers_stopped": False}
    containers = []
    docker = shutil.which("docker")
    try:
        report["before"] = binding()
        if sys.flags.optimize:
            raise RuntimeError("OPTIMIZATION_NOT_ALLOWED")
        if sys.platform != "linux":
            raise RuntimeError("LINUX_EXECUTION_REQUIRED")
        if not docker:
            raise RuntimeError("DOCKER_REQUIRED")
        config = {"pg_host": "127.0.0.1", "pg_user": "c10_test",
                  "pg_password": secrets.token_hex(24), "c10_database": "c10_" + run_id,
                  "redis_host": "127.0.0.1", "redis_password": secrets.token_hex(24),
                  "redis_database": 0}
        config_path = output / "connections.json"
        # Config files remain private/local, never part of the uploaded report.
        config_path.write_text(json.dumps(config))
        pg_name, redis_name = "c10-ci-" + run_id + "-pg", "c10-ci-" + run_id + "-redis"
        label = "ba.c10.phase.run=" + run_id
        def create(name, image, args):
            containers.append(name)  # Reconcile uncertain create outcomes by unique name.
            report["active_stage"] = "create_" + name.rsplit("-", 1)[-1]
            result = invoke([docker, "run", "-d", "--platform", "linux/amd64",
                             "--name", name, "--label", label, "--memory", "512m", *args, image],
                            timeout=600)
            ident = result.stdout.strip()
            return ident
        pg_id = create(pg_name, PG_IMAGE,
                       ["-p", "127.0.0.1::5432", "-v", pg_name + "-data:/var/lib/postgresql/data",
                        "-e", "POSTGRES_USER=" + config["pg_user"],
                        "-e", "POSTGRES_PASSWORD=" + config["pg_password"],
                        "-e", "POSTGRES_DB=" + config["c10_database"]])
        redis_id = create(redis_name, REDIS_IMAGE,
                          ["-p", "127.0.0.1::6379", "-v", redis_name + "-data:/data",
                           "-e", "REDIS_ARGS=--appendonly yes --maxmemory 256mb "
                                 "--maxmemory-policy allkeys-lru --requirepass " + config["redis_password"]])
        def update_ports():
            for ident, target, key in ((pg_id, "5432/tcp", "pg_port"),
                                       (redis_id, "6379/tcp", "redis_port")):
                config[key] = int(invoke([docker, "port", ident, target]).stdout.strip().rsplit(":", 1)[1])
            config_path.write_text(json.dumps(config))
        update_ports()
        import psycopg
        import redis
        def wait_ready():
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    with psycopg.connect(host=config["pg_host"], port=config["pg_port"],
                                         user=config["pg_user"], password=config["pg_password"],
                                         dbname=config["c10_database"], connect_timeout=2) as db:
                        assert db.execute("SELECT 1").fetchone()[0] == 1
                        pg_version = db.execute("SHOW server_version").fetchone()[0]
                    client = redis.Redis(host=config["redis_host"], port=config["redis_port"],
                                         password=config["redis_password"], socket_timeout=2, decode_responses=True)
                    try:
                        assert client.ping()
                        module_rows = client.module_list()
                        modules = {m["name"] for m in module_rows}
                        assert "search" in modules and "ReJSON" in modules
                        report["stores"] = {
                            "postgres_version": pg_version,
                            "redis_version": client.info("server")["redis_version"],
                            "redis_modules": [{"name": m["name"], "version": m["ver"]}
                                              for m in module_rows],
                        }
                    finally:
                        client.close()
                    return
                except Exception:
                    time.sleep(1)
            raise RuntimeError("ISOLATED_STORES_NOT_READY")
        wait_ready()
        env = environment(config, "postgres", output)
        def child(name, args, child_env=env):
            report["active_stage"] = name
            if (output / ".env").exists() or (output / ".env").is_symlink():
                raise RuntimeError("FIXTURE_ENV_FILE_REJECTED")
            try:
                result = invoke([sys.executable, "-B", *args], env=child_env,
                                timeout=240, cwd=output)
            except subprocess.CalledProcessError as exc:
                (output / (name + ".stdout")).write_text(exc.stdout or "")
                (output / (name + ".stderr")).write_text(exc.stderr or "")
                raise RuntimeError("CHILD_FAILED_" + name) from None
            (output / (name + ".stdout")).write_text(result.stdout)
            (output / (name + ".stderr")).write_text(result.stderr)
            return result.stdout
        child("schema", ["-m", "app.core.db_bootstrap", "apply", "--execute"])
        child("saver-setup", ["-m", "app.graph.checkpointer", "setup-postgres", "--execute"])
        def record(case, value):
            checks = value.get("checks", [])
            assert value.get("status") == "PASS"
            assert len(checks) == EXPECTED[case] and all(c.get("pass") is True for c in checks)
            assert len({c["name"] for c in checks}) == len(checks)
            assert {c["name"] for c in checks} == set(EXPECTED_CHECKS[case])
            assert value.get("before") == value.get("after")
            report["cases"][case] = {"status": "PASS", "assertions": len(checks),
                                    "checks": checks}
        for backend, case in (("postgres", "C10-PG-BASE"), ("redis", "C10-REDIS-BASE")):
            value = json.loads(child(case, [str(HERE / "baseline.py")],
                                     environment(config, backend, output)))
            record(case, value)
        fault_index = json.loads(child("C10-PG-FAULT", [str(HERE / "faults.py")]))
        fault_path = Path(fault_index["receipt"])
        assert fault_path.resolve().is_relative_to(output.resolve())
        record("C10-PG-FAULT", json.loads(fault_path.read_text()))
        before_index = json.loads(child("restart-before", [str(HERE / "restart.py"), "before",
                                                           str(fault_path)]))
        assert before_index["status"] == "PASS"
        # Restart only this exact newly-created fixture after confirming its unique label.
        actual = json.loads(invoke([docker, "inspect", pg_id]).stdout)[0]
        assert actual["Config"]["Labels"]["ba.c10.phase.run"] == run_id
        invoke([docker, "restart", pg_id], timeout=60)
        update_ports()
        wait_ready()
        env.update(environment(config, "postgres", output))
        after_index = json.loads(child("restart-after", [str(HERE / "restart.py"), "after",
                                                         before_index["receipt"]]))
        after_path = Path(after_index["receipt"])
        assert after_path.resolve().is_relative_to(output.resolve())
        record("C10-PG-RESTART", json.loads(after_path.read_text()))
        report["versions"] = {name: importlib.metadata.version(name) for name in
                              ("psycopg", "langgraph-checkpoint", "langgraph-checkpoint-postgres",
                               "langgraph-checkpoint-redis", "redis", "msgpack", "setuptools")}
        report["images"] = []
        for ident in containers:
            info = json.loads(invoke([docker, "inspect", ident]).stdout)[0]
            report["images"].append({"configured_image": info["Config"]["Image"], "image_id": info["Image"]})
        report["active_stage"] = "complete"
        report["phase_execution"] = "PASS"
    except BaseException as exc:
        report["failure_type"] = type(exc).__name__
        report["phase_execution"] = "FAIL"
    finally:
        stopped = True
        if docker:
            for ident in containers:
                try:
                    inspected = subprocess.run([docker, "inspect", ident], cwd=REPO,
                                               capture_output=True, text=True, timeout=15)
                    if inspected.returncode:
                        absent = {"Error: No such object: " + ident,
                                  "Error response from daemon: No such container: " + ident}
                        if (inspected.returncode == 1 and inspected.stderr.strip() in absent
                                and inspected.stdout.strip() in {"", "[]"}):
                            continue
                        raise RuntimeError("FIXTURE_STOP_OUTCOME_UNCERTAIN")
                    info = json.loads(inspected.stdout)[0]
                    assert info["Config"]["Labels"]["ba.c10.phase.run"] == run_id
                    invoke([docker, "stop", ident], timeout=60)
                except Exception:
                    stopped = False
        report["containers_stopped"] = stopped
        try:
            report["after"] = binding()
            report["candidate_binding"] = ("PASS" if report.get("before") == report["after"]
                                             and report["after"]["clean"] else "BLOCKED")
        except Exception:
            report["candidate_binding"] = "BLOCKED"
        if set(report["cases"]) != set(EXPECTED) or not stopped:
            report["phase_execution"] = "FAIL"
        (output / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({"phase_execution": report["phase_execution"],
                          "candidate_binding": report["candidate_binding"],
                          "full_c10_acceptance": False,
                          "report": str((output / "report.json").relative_to(REPO))}))
    return 0 if report["phase_execution"] == report["candidate_binding"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
