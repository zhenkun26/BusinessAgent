"""Offline CI safety checks; no Docker, network, file cleanup or package installation."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
phase = sys.argv[1]
if phase not in ("ci-baseline", "ci-final"):
    raise SystemExit("Choose ci-baseline or ci-final")
source = WORKFLOW.read_text()
workflow = yaml.load(source, Loader=yaml.BaseLoader)
job = workflow["jobs"]["docker"]
steps = job["steps"]
build_i, build = next(
    (i, s) for i, s in enumerate(steps)
    if s.get("uses", "").startswith("docker/build-push-action@")
)
scan_i, scan = next(
    (i, s) for i, s in enumerate(steps)
    if s.get("uses", "").startswith("aquasecurity/trivy-action@")
)
login_i, login = next(
    (i, s) for i, s in enumerate(steps)
    if s.get("uses", "").startswith("docker/login-action@")
)
publish_steps = [(i, s) for i, s in enumerate(steps) if "docker push" in s.get("run", "")]
commit_tag = "ghcr.io/${{ github.repository_owner }}/businessagent:${{ github.sha }}"
checks = {
    "build_never_publishes": build["with"].get("push") == "false",
    "scan_uses_loaded_commit_image_only": (
        build["with"].get("load") == "true"
        and commit_tag in build["with"]["tags"].splitlines()
        and scan["with"].get("image-ref") == commit_tag
        and scan.get("env", {}).get("TRIVY_IMAGE_SRC") == "docker"
        and build_i < scan_i
    ),
    "scan_blocks_failures": (
        scan["with"].get("exit-code") == "1"
        and scan["with"].get("severity") == "HIGH,CRITICAL"
        and scan.get("continue-on-error", "false") == "false"
        and job.get("continue-on-error", "false") == "false"
    ),
    "authentication_follows_scan_on_successful_push_only": (
        scan_i < login_i and login.get("if") == "github.event_name == 'push'"
    ),
    "publication_follows_scan_on_successful_push_only": (
        len(publish_steps) == 1
        and scan_i < login_i < publish_steps[0][0]
        and publish_steps[0][1].get("if") == "github.event_name == 'push'"
        and publish_steps[0][1].get("shell") == "bash"
    ),
    "failed_scan_report_retained": any(
        i > scan_i and s.get("if") == "always()"
        and s.get("uses", "").startswith("actions/upload-artifact@")
        and s.get("with", {}).get("path") == "trivy-report.txt"
        for i, s in enumerate(steps)
    ),
}
shell_runs = []
if len(publish_steps) == 1:
    publish = publish_steps[0][1]
    script = publish["run"]
    checks["publish_environment_matches_built_image"] = (
        publish.get("env", {}).get("IMAGE")
        == "ghcr.io/${{ github.repository_owner }}/businessagent"
    )
    # Abort verification before executing any unexpected shell command.
    checks["publish_only_pushes_existing_tags"] = script.splitlines() == [
        'docker push "$IMAGE:$GITHUB_SHA"', 'docker push "$IMAGE:latest"'
    ]
    if checks["publish_only_pushes_existing_tags"]:
        for fail_first in (False, True):
            stub = (
                'IMAGE=ghcr.io/example/businessagent\nGITHUB_SHA=test-sha\n'
                'docker() { printf "%s\\n" "$*"; '
                + ('return 23;' if fail_first else 'return 0;') + ' }\n'
            )
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-s"],
                input=stub + script, text=True, capture_output=True, check=False,
            )
            expected = ["push ghcr.io/example/businessagent:test-sha"]
            if not fail_first:
                expected.append("push ghcr.io/example/businessagent:latest")
            checks["first_push_failure_stops_latest" if fail_first else "both_tags_pushed"] = (
                result.stdout.splitlines() == expected
                and result.returncode == (23 if fail_first else 0)
            )
            shell_runs.append({"fail_first": fail_first, "exit_code": result.returncode,
                               "commands": result.stdout.splitlines()})
payload = {
    "phase": phase, "workflow_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "checks": checks, "shell_runs": shell_runs,
    "passed": all(checks.values()),
    "limits": "Offline structure and fake-Docker shell checks only; Actions/Docker not executed.",
}
with Path(__file__).with_name(phase + ".json").open("x") as out:
    json.dump(payload, out, indent=2)
    out.write("\n")
print(json.dumps(payload, indent=2))
raise SystemExit(0 if payload["passed"] else 1)
