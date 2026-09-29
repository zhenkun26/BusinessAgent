## Context

Starting commit: e8512e9f7c4f3c6e9058579bfa2dd90c5dd1a440. The prior FGR-01/FAT-01
cleanup is complete and unchanged. `.github/workflows/ci.yml` currently combines build
and push, then scans `latest`. Docker CLI, actionlint and OpenSpec CLI are unavailable
locally; existing PyYAML can support offline workflow checks without installation.

## Decisions

1. Keep docker/build-push-action with `load: true`, but set `push: false` for all events.
2. Trivy scans the commit tag from the local Docker daemon (`TRIVY_IMAGE_SRC=docker`).
   It must not scan an older registry image or the mutable `latest` tag.
3. Put GHCR login and explicit `docker push` commands after the scan, gated by normal
   successful-step semantics and the existing push-event condition. Push the commit
   tag before `latest`; do not rebuild between scanning and publication.
4. Preserve Python tests, gitleaks, pip-audit, vulnerability exemptions, severity,
   ignore-unfixed policy and always-upload scan reporting. No production deployment.
5. Validate structural safety properties and execute the publication shell with a fake
   Docker function, including first-push failure. Real builds/scans run on the PR.

6. PR run 36516997345 passed 143 tests on each Python version but failed gitleaks
   before scanning: the default shallow checkout lacks the requested commit range.
   Set fetch-depth to 0 for the test checkout, as in the upstream gitleaks-action
   example. Preserve scanner policy and permissions.

## Limits

Offline checks do not execute GitHub Actions or Docker. Cloud PR checks are required
before merging, and main-push checks are required to confirm publication. One approving
GitHub review is required; agent review is not a substitute, and no admin bypass is allowed.

OpenSpec artifacts are maintained manually because its CLI is unavailable. Do not claim
`openspec validate --strict` passed. Archive completed implementation evidence separately
from pending GitHub integration, without deleting files or branches.
