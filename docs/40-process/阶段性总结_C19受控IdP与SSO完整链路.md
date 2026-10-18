# C19 — Controlled IdP and SSO integration candidate

Date: 2026-10-18. Branch: `codex/delivery-ci-gates`.
Scope: local implementation, documentation and offline verification; C19 remains open.

## Authorization and delivery

C18 `bd04a120daf6695f5b735bcd73733c0e2def07b1` was pushed to the same remote branch
and verified before C19. The user authorized C19 only and subsequently approved
PyJWT[crypto], cryptography 50.0.2 and required transitive declarations/import probes.
No dependency was installed, image built, key generated or actual IdP/signature executed.
C19 push, C20, merge, deployment, release and OpenSpec sync/archive are not authorized.

The candidate delivers:

- Independent HTTPS reference issuer with environment-only synthetic identities/keys,
  exact client/redirect/S256 bindings, atomic expiring single-use authorization codes,
  retained SQLite state, separate operator listener, key publication and request-scoped faults.
- Fixed RS256 and exact-key application verification, bounded verified HTTPS transport,
  strict issuer/audience/azp/nonce/time/subject checks and PKCE stored with shared Redis state.
- Exact issuer/subject identity mapping, first-login salesperson/local department, no linking
  by username/email or authority from remote claims, disabled-account denial and protection
  of mapped accounts against development passwordless login. Existing local identity/role
  stays authoritative. Legacy normalized/truncated mapping review remains a runtime gate.
- Separate non-root image and loopback TLS gateway/Compose/env recipes, no automatic keys
  or initialization, and final-image crypto imports. Dependency resolution/build/scan unrun.
- S01–S16 browser/operator matrix and plan/report entry. Reports preserve reported status
  separately and never turn metadata or operator assertions into runtime acceptance.
- Updated OpenSpec delta/tasks, roadmap, issue criteria, baseline, authority context,
  decisions, safety review and documentation indexes.

See [contract, isolation recipe and acceptance matrix](../50-engineering/controlled-sso.md).

## Verification

| Check | Result | Evidence boundary |
| --- | --- | --- |
| C19 `run_c19_controlled_sso.py` | PASS, 37 cases | Actual source; in-memory SQLite; signer/PyJWT/HTTP/Redis/PG/framework doubles |
| C05 runtime authorization | PASS, 29 cases | Existing startup/identity/approval fail-closed contracts |
| C06 credential safety | PASS, 20 cases | Sanitized diagnostics; existing datetime.utcnow deprecation warning remains |
| C09 shared runtime state | PASS, 28 cases | Independent module instances and shared in-memory Redis doubles |
| C18 reference integration | PASS, 45 cases | Independent service code with memory/transport dependencies injected |
| C06 browser script | PASS, 14 cases | Node VM, not DOM/browser/SSO execution |
| Changed Python AST / manifest / links / OpenSpec structure / diff | PASS | Static checks; not strict OpenSpec CLI or Compose validation |
| Safe validator | Execution PASS, overall BLOCKED | Expected exit 2; formal UAT and release flags false |
| Full pytest, strict OpenSpec CLI, Docker/Nginx configuration/build/scan | BLOCKED | Tools/dependencies unavailable; installation/build outside approved scope |
| Real PyJWT/cryptography signing/verification, TLS and S01–S16 browser chain | BLOCKED | No real keys, issuer, browser or services executed |
| Real PG/Redis/two-process state, disk restart/fault recovery and full RAG | BLOCKED | Offline checks cannot prove these properties |

37 focused + 136 related cases pass. Tests cover exact bindings, spent-code concurrency,
claim failures, key-selection/retirement logic, least-privilege/collision mapping, callback
consumption/replay, bounded transport and sanitized reports. The signer intentionally emits
a non-cryptographic signature; mocked decode success is never RSA verification evidence.
SQLite tests reopen the same in-memory connection, not a disk/process restart. A source-level
production-setting check confirms invalid SSO profiles reach startup rejection.

Commands run from the repository root use `python3.13 -I -B enterprise-agent/eval/<entry>`
and `node enterprise-agent/tests/test_browser_credential_safety.cjs`. Tests audit-block disk
database creation, writes/deletion, network and subprocesses. The safe validator stays on its
existing five-function allowlist; C19 is separately reviewed and does not weaken those gates.
The final candidate/source-hash receipt is retained in ignored `enterprise-agent/eval/results/`.

## Retained limitations and stop point

All S01–S16 and C18 R01–R20 are BLOCKED; unimplemented fault-proxy subcases and operator
review requirements remain explicit in the matrix. No plan, template, current key metadata
or user-supplied report proves real login or an image identity. Reference success would still
not accept enterprise SSO/UAT. Physical PERSIST/FULL behavior and journal retention require
observation; retained events record rotation occurrence, so before/after snapshots are needed.

This is a single-client, single-replica, bounded reference IdP with fixed synthetic fixtures;
no MFA, userinfo, refresh, registration, HA or performance claim. Existing application audit
cache deletion is unchanged and deferred to C21; review it before runtime launch under the
non-deletion policy. No files/data/volumes were deleted or reset. The 556 pre-existing
executable-mode-only changes are preserved and excluded from this increment.

C10 lease-expiry checkpoint writing remains unresolved and stays in C10. C15/C16/C17/C18/C19
remain open; all earlier real runtime, full RAG, browser/SSO and historical credential gates
remain BLOCKED. `formal_uat=false`, `release_evidence=false`, `release_allowed=false`.
Stop after the C19 local commit and wait for confirmation before its push or C20.
