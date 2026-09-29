# Scan before image publication

## Scope and authorization

Follow-up to the backend simplification commit `e8512e9`. The user authorized this CI
repair, temporary cleanup on cloud runners/in build images, PR creation, merge under
branch protection and GHCR publication. Local deletion remains prohibited; production
deployment is not authorized. The 556 unrelated executable-mode changes are preserved.

The existing `security-operations` specification already requires vulnerability scans
to block publication. This fixes its implementation without changing the main specification,
application behavior, dependencies, vulnerability policy or branch protection.

## Change

The previous build-push step could update both GHCR tags before Trivy rejected the image.
CI now builds and loads without pushing, scans the local commit-tagged image using only
the Docker source, then logs in and pushes that same image. No rebuild occurs between
scan and push. The commit tag is pushed before `latest`; PR and manual runs do not publish.
Normal Actions success gating skips login/publication after any failed prior step.
The scan report retains its `always()` upload condition.

## Verification

From the repository root, reusing already-installed PyYAML 6.0.3:

```sh
PYTHONPATH=enterprise-agent/.venv/lib/python3.13/site-packages python -B docs/40-process/code-simplification/20260928-backend/verify_ci.py ci-baseline
PYTHONPATH=enterprise-agent/.venv/lib/python3.13/site-packages python -B docs/40-process/code-simplification/20260928-backend/verify_ci.py ci-final
```

- `ci-baseline.json`: expected exit 1 on the original workflow, identifying build-time
  publication, mutable scan target, early authentication and absent post-scan publication.
- `ci-final.json`: exit 0, all 10 safety checks pass. The publication shell executes with
  a fake Docker function: success pushes both expected tags; first-push exit 23 stops before
  `latest`. These commands do not run Docker or publish anything.
- Workflow hashes bind each result to its input. Evidence files use exclusive creation
  and are retained, including the failing baseline. No packages were installed locally.
- Original FGR-01/FAT-01 source and test files are unchanged since the verified cleanup.

Independent final review found no blocking issues; it separately checked Trivy's source
selection and Actions success gating and repeated both fake-Docker shell cases. Workflow
hashes, Python AST and final diff checks passed. Docker, actionlint and OpenSpec CLI
are unavailable locally. The offline checks are structural and shell checks, not a real
Actions execution or a Docker/Trivy pass. Cloud PR CI must pass before merge; the subsequent
main run must succeed to confirm image publication. The required approving GitHub review
cannot be supplied by an agent review or bypassed with administrator privileges.

## Delivery status

Implementation verified on `codex/simplify-backend-internals`; PR, cloud checks, protected
merge and publication are pending. OpenSpec implementation artifacts are archived at
`openspec/changes/archive/2026-09-28-scan-image-before-publish/` after local verification
and review. GitHub integration status is tracked on the PR rather
than claimed complete in this local verification report.
