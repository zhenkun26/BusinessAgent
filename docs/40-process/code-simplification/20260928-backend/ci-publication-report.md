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

## Cloud PR validation and history repair

[PR #1](https://github.com/zhenkun26/BusinessAgent/pull/1) was created with commit `7feb94a`.
[Run 36516997345](https://github.com/zhenkun26/BusinessAgent/actions/runs/36516997345)
passed 143 tests on both Python 3.11 and 3.13. Both jobs then failed gitleaks before any
meaningful scan: the default shallow checkout lacked the requested `e8512e9^..7feb94a`
history (`unknown revision`). Docker and Trivy were skipped. This was a scanner setup
failure, not a clean secret-scan result and not an image-build result.

The test job now uses `fetch-depth: 0`, matching the upstream gitleaks-action example,
so the PR range is available. Scanner policies and permissions remain unchanged.
The same verifier now accepts numbered attempts and checks complete scanner history:

```sh
PYTHONPATH=enterprise-agent/.venv/lib/python3.13/site-packages python -B docs/40-process/code-simplification/20260928-backend/verify_ci.py ci-baseline-02
PYTHONPATH=enterprise-agent/.venv/lib/python3.13/site-packages python -B docs/40-process/code-simplification/20260928-backend/verify_ci.py ci-final-02
```

The new baseline exits 1 solely for missing history; the repaired workflow exits 0 with
all 11 checks passing. Both earlier JSON files remain unchanged. A new cloud run is still
required; successful local verification does not replace it. Independent follow-up review
confirmed this fixes the missing history without changing scanner policy or publication gates.

## Delivery status (updated 2026-09-29)

PR #1 merged as `2d4bfc17a34e45907404fdde38857e4cf96ad550` after the owner explicitly
authorized an administrator exception for that PR only. The exception did not change
branch protection and does not authorize bypasses on later PRs.

[Main CI 36522224892](https://github.com/zhenkun26/BusinessAgent/actions/runs/36522224892)
passed 143 tests on each Python version, gitleaks, pip-audit, image build, Trivy and
publication. Trivy completed at 04:37:55 UTC before publication, which completed at
04:38:14 UTC on 2026-09-29. Both Docker push logs and
[GHCR metadata](https://github.com/users/zhenkun26/packages/container/businessagent/1308617299)
confirm that the merge-commit tag and `latest` reference
`sha256:9bcc1e277b43897907e2a2a341b9b42631909d58c9614fe63e55a42bda8302c8`.

Both OpenSpec implementation changes are archived and present on GitHub. Local main was
synchronized to the merge commit with all 556 pre-existing mode changes and the feature
branch preserved. No local filesystem deletion or production deployment occurred.
The initial offline and failed-cloud attempts above remain historical evidence.
