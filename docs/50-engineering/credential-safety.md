# C06 credential lifecycle and safe output contract

Status: offline increment implemented, 2026-10-17. **C06 remains open. Real JWT,
PostgreSQL, API/SSE, Linux, browser/IdP and historical remediation are BLOCKED.**

## Authorization without stored login credentials

The supported flow is now: requester creates an approval → authorized approver
records a decision → requester reviews it and explicitly confirms execution with
their current bearer credential. Single and batch approval always enter
`approved_pending_reauth`; they do not execute tools. The status name is preserved
for compatibility, but it now means requester confirmation is required regardless
of whether the original login expired. UI actions say “确认执行”.

Resume verifies the supplied token after acquiring current-account authorization
locks and requires its subject to match the requester. The original approver must
still exist, be active and have approval permission; requester tool permissions
must still apply. C05's fail-closed account checks remain. Approval decisions record
the approver and confirmation requirement in audit; execution records the original
approver and actual requester identity. C11 atomic claiming and idempotency remain
unimplemented: concurrent duplicate resume is not claimed safe.

Application bearer credentials stop at the authentication/resume boundary. They
are absent from `UserContext`, `UserInput`, execution-agent instances and tool
context. New approval INSERTs omit `requester_token`; decision/resume SELECTs and
UPDATEs never use it. The nullable legacy column remains to avoid an unapproved
schema/data migration. Service-specific HTTP API keys still come from settings
and are sent only to the configured external service, not as user delegation.

Recognized credential strings in user chat input, graph input messages, approval
payloads and summaries are masked before persistence/truncation. Credentials must
not be supplied as ordinary business parameters; masking can intentionally change
such payloads. This is not an arbitrary secret/PII classifier.

## Diagnostic boundaries

[redaction.py](../../enterprise-agent/app/security/redaction.py) makes JSON-safe
copies, masking sensitive field names, bearer/JWT forms, credential assignments,
URL userinfo, explicitly supplied transport keys and configured secret values.
Settings loaded from `.env` register their secret fields without logging them;
environment secret strings of at least eight characters are also recognized.
Unknown objects are not stringified. The policy does not guarantee detection of
arbitrary unlabeled/encoded secrets, partial strings or sensitive business prose.

| Sink | Behavior |
| --- | --- |
| Audit database | Recursively redact before summary truncation and JSON serialization |
| Audit local fallback and replay | Apply the same redactor before writing or replaying; tests use in-memory files only |
| API/worker Loguru | Install a record patcher before other application imports; redact message/extra and omit exception traceback/locals; patch failure emits a fixed code |
| Application tracing helpers | Redact attributes/events; record fixed exception message; owned spans disable automatic raw exception recording |
| SQLAlchemy engine | Disable SQL echo and hide bind parameters in SQL diagnostics |
| HTTP tools | Never return provider 4xx response bodies or URL credentials; redact successful payloads, including exact transport-key echoes |
| Tool gateway and compensation | Sanitize returned output/error/side-effects and audit input; validation/execution/compensation exceptions use fixed codes |
| HTTP/SSE errors | Fixed request/validation/chat/history failure codes; no exception text or validation input reflection |

The tracing context now enters once, sanitizes attributes inside that context, and
leaves automatic raw exception recording disabled. Third-party automatic telemetry,
SDK/stdout/access logs and actual exporter behavior still require live marker tests;
this increment does not claim every external logging sink is certified safe.
Existing audit replay still has its prior cleanup behavior; **do not run replay
against filesystem data in this workflow**. No cache file was removed here.

## Browser and HTML behavior

- Normal login tokens and passwords are not written to localStorage/sessionStorage.
  Tokens live in the Vue application's memory; passwords are cleared on completion
  and logout. The login form now supplies the required password.
- SSO's HTML response uses one `sessionStorage` handoff, consumed and removed when
  the UI loads. It is never in a URL. A further reload requires login. Existing
  localStorage auth/session keys are discarded when this UI loads. Tab restoration
  before the handoff is consumed is not treated as a proven secure erasure boundary.
- Logout/401 clears identity, chat/approval state and sensitive UI drafts, aborts
  streaming and invalidates stale responses. Auth responses use `Cache-Control:
  no-store`. Client logout does **not** revoke a stolen signed token server-side;
  C05 account disabling and signing-key rotation remain the current revocation tools.
- Browser memory and the one-time SSO handoff remain accessible to same-origin
  scripts; this is not an HttpOnly-cookie session implementation or an XSS immunity
  claim. Third-party CDN scripts remain an explicit unverified supply-chain surface.
- Markdown output uses DOMPurify only after a string result from the renderer. If
  either library is absent, unsupported, throws or returns a non-string, original
  text is escaped (`& < > " '`) before `v-html`. No raw-HTML fallback is allowed.

## Historical credentials and acceptance procedure

No existing database, checkpoint, log/cache, backup or browser profile was opened,
rewritten, migrated or deleted. Ignoring the legacy column does not erase it, and
new code cannot sanitize already stored checkpoints retroactively. Before allowing
real use of an upgraded environment, separately authorize an operator procedure:

1. Inventory affected stores and backups by counts/record identifiers and retention
   class only; never dump token values into evidence. Include the legacy approval
   column, graph checkpoints, audit fallback files and prior browser persistence.
2. Revoke exposed credentials: rotate the application signing key across API/worker
   and all validators, and rotate affected external service keys. Coordinate logout
   and recovery; no rotation is executed by this change.
3. Approve a data-retention/remediation plan for old columns, checkpoints and backups.
   Until then, do not resume legacy checkpoint histories or claim migration complete.
   No filesystem deletion is automated or authorized by this document.
4. Use an isolated database/new conversation namespace and synthetic identities to
   verify both approval paths and resume, wrong-subject/expired/disabled/downgraded
   identities, lock waits and duplicate attempts. Check resulting SQL/checkpoints
   for marker absence without recording live secrets.
5. Inject synthetic marker credentials into nested tool/audit/provider outputs and
   exceptions; inspect DB, local fallback/replay, application/server/SDK logs, trace
   exporters, error responses and SSE. Include `.env` values and split/encoded data;
   record policy limits instead of claiming untested patterns pass.
6. In a real browser, check malicious HTML in normal and failure paths, DOMPurify and
   renderer failures, password login, SSO handoff, reload, logout, concurrent stale
   responses and SSE 401. Bind browser/library versions and candidate commit/image.

Offline entries, from the repository root:

```bash
python3 -I -B enterprise-agent/eval/run_c06_credential_safety.py
python3 -I -B enterprise-agent/eval/run_c05_runtime_authorization.py
node enterprise-agent/tests/test_browser_credential_safety.cjs
```

These execute actual source/functions with injected dependencies and actual inline
UI script in a Node VM. They do not prove real cryptography, SQL transactions,
browser DOM execution, network/SSO, telemetry export or historical cleanup.
