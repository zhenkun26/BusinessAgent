"""Check resolved Compose JSON from stdin; never echo its environment or credentials."""

from __future__ import annotations

import json
import re
import sys
from typing import Any


def check_contract(config: dict[str, Any]) -> dict[str, Any]:
    """Validate artifact identity and exposure, not runtime health or image provenance."""
    services = config["services"]
    api, worker = services["api"], services["worker"]
    applications = [api, worker] + ([services["api2"]] if "api2" in services else [])
    worker_probe = ["CMD", "python", "-B", "-c",
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/ready', timeout=6)"]
    digest = api.get("image", "")
    checks = {
        "immutable_application_image": isinstance(digest, str)
        and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[0-9a-f]{64}", digest)
        is not None,
        "api_worker_same_image": all(item.get("image") == digest for item in applications),
        "no_application_build": all("build" not in item for item in applications),
        "no_application_host_ports": all(not item.get("ports") for item in applications),
        "private_application_network": all(
            item.get("network_mode") != "host" for item in applications
        ),
        "image_entrypoint_preserved": all(
            item.get("entrypoint") is None for item in applications
        ),
        "no_application_source_mounts": all(
            not item.get("volumes_from")
            and not item.get("configs")
            and not item.get("secrets")
            and not item.get("tmpfs")
            and all(
                isinstance(mount, dict)
                and mount.get("type") == "volume"
                and mount.get("target") in {"/data/hf_cache", "/app/logs", "/app/audit_logs", "/data/observability"}
                for mount in item.get("volumes", [])
            )
            for item in applications
        ),
        "worker_uses_own_readiness_probe": worker.get("healthcheck", {}).get("test") == worker_probe
        and worker.get("healthcheck", {}).get("disable") is not True,
        "shared_retained_audit_volume": all(
            item.get("environment", {}).get("OBSERVABILITY_STORE_PATH")
            == "/data/observability/state.sqlite3"
            and any(mount.get("type") == "volume"
                    and mount.get("target") == "/data/observability"
                    and mount.get("source") == "audit_state"
                    and not mount.get("read_only", False)
                    for mount in item.get("volumes", []) if isinstance(mount, dict))
            for item in applications),
    }
    return {
        "scope": "C01-resolved-compose-contract",
        "overall_status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "runtime_verified": False,
        "release_allowed": False,
    }


def main() -> int:
    try:
        report = check_contract(json.load(sys.stdin))
    except (ValueError, KeyError, TypeError, AttributeError):
        print(json.dumps({"overall_status": "FAIL", "error_code": "INVALID_COMPOSE_MODEL"}))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
