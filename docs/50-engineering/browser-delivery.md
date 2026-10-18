# C20 — Browser delivery and role acceptance

Date: 2026-10-18. Candidate only; **C20 remains open**. All B01–B16 below are
**BLOCKED**. Node VM/static checks are not browser, DOM, API, SSO or deployment evidence.
This profile adds no new frontend framework or administrative page. See the
[delivery baseline](engineering-delivery-baseline.md), [C19 SSO profile](controlled-sso.md)
and [C18 reference integration](reference-integration.md) for independent runtime gates.

## Delivered artifact and reproducibility

Serve the application through the same-origin `/ui/` entry in the C01 Linux/Nginx recipe.
Opening the HTML as a local file is unsupported. Production HTTPS is required for the
SSO profile. No frontend build tool, npm install or public CDN is required at runtime.

The existing three browser dependencies are now retained under
`enterprise-agent/app/static/vendor/`, with exact versions and upstream license files:

| Package | Browser distribution | License |
| --- | --- | --- |
| Vue 3.5.44 | `vue.global.prod.js` | MIT |
| Marked 18.1.1 | `marked.umd.js` | MIT |
| DOMPurify 3.4.17 | `purify.min.js` | MPL-2.0 OR Apache-2.0 |

The files came from the official npm version metadata for
[Vue](https://registry.npmjs.org/vue/3.5.44),
[Marked](https://registry.npmjs.org/marked/18.1.1) and
[DOMPurify](https://registry.npmjs.org/dompurify/3.4.17). Tarball SHA-512 was compared
with registry integrity before selected JS/license members were retained. The manifest
records source URL, registry integrity, per-file SHA-256 and SHA-384 SRI. This verifies
consistency with those downloads, not upstream trust, vulnerability clearance or attestations.
Vue uses its [production global build](https://vuejs.org/guide/best-practices/production-deployment.html).
Markdown still passes through [DOMPurify](https://github.com/cure53/DOMPurify); missing or
throwing parsing/sanitization falls back to escaped text. No remote fallback is configured.

The HTML references exact local paths and SRI. Missing Vue leaves a static failure message
and a cloaked application; no-JavaScript has a separate explanation. A missing sanitizer
must not cause raw HTML rendering. Dockerfile.prod copies the verifier and runs it after
copying `app/`. No image was built in this increment; served paths, browser SRI enforcement,
Vue template mounting and real DOM sanitization remain B01/B14/B16 work.

Reviewed, read-only commands from the repository root:

```bash
python3.13 -I -B enterprise-agent/scripts/verify_frontend_assets.py enterprise-agent/app/static
node enterprise-agent/tests/test_browser_delivery.cjs
node enterprise-agent/tests/test_browser_credential_safety.cjs
```

The verifier checks all seven retained JS/license files, safe manifest paths and exact HTML
script/SRI references. The Node entry reads actual page source and distributions, injects
browser/HTTP doubles and executes Marked in a VM. It neither starts a browser/server nor
loads the application, installs dependencies, makes network calls, writes or deletes files.
Vue/DOMPurify syntax checks do not prove DOM behavior. Dependency updates must deliberately
refresh exact artifacts, license files, manifest and SRI, then repeat offline and browser
acceptance; never replace URLs with floating versions. Old retained files are not automatically
deleted. Dependency advisory/image scanning remains unrun.

## Identity, role and data contract

Local login and the one-shot SSO handoff supply only an in-memory token; `/auth/me` must
confirm the current local identity before opening the workspace. Handoff/login role claims
are not authority. Management actions recheck `/me`; changed user, role or department ends
the session. The backend still owns authorization on every request (C05). A page can show
old controls until its next request; hiding controls is not a security boundary.

Logout clears identity, protected lists, conversation and pending UI state. Request and
conversation generations prevent late replies from repopulating another login/session.
Refresh requires a new login; no persistent browser token/session recovery was introduced.
Picker entries are synthetic examples, not automatically provisioned accounts or permission
assignments. Use real passwords from explicit C03 provisioning; passwordless development
behavior is not this delivery profile.

| Surface | Sales | Customer service | Finance | Manager | Admin | Server requirement |
| --- | --- | --- | --- | --- | --- | --- |
| Conversation, own history, feedback, own approvals | Yes | Yes | Yes | Yes | Yes | Current identity, ownership and operation permissions |
| Pending/handled approval controls | Hidden | Hidden | Hidden | Visible | Visible | Per-row approver role/current state; admin exception as implemented |
| Prompt list/create/activate/traffic | Hidden | Hidden | Hidden | Visible | Visible | Manager/admin dependency on all routes |
| Document ledger | Hidden | Hidden | Hidden | Hidden | Visible | Admin dependency; no synthetic fallback |
| User and knowledge administration writes | API only, denied | API only, denied | API only, denied | API only, denied | API only | Admin dependency |
| Synthetic customer/order/ticket examples | Visible | Visible | Visible | Visible | Visible | Explicitly static; not current provider records |
| Component observations | Visible | Visible | Visible | Visible | Visible | `/ready` is public; not a complete C21 readiness guarantee |

Do not require every approval list to return 403 for ordinary roles: the authenticated API
filters rows by approver roles/ownership. Test unauthorized *records and mutations* as well
as controls. Pending/handled lists use the existing bounded default (50); the UI document
ledger requests 100 rows. There is no complete paginated administration UI. Use the API
pagination for full inventories and record the selected IDs. History is a final snapshot
with session status, not a full transcript or independent proof of business execution.

## Failure and action states

- JSON requests have a 15-second abort timeout, no automatic write retry, fixed HTTP error
  text, object-shape validation and a 2 Mi-character check after response text is read.
  That last check is not a streaming memory bound. Timeout does not cancel server-side work.
- A pending action blocks duplicate clicks. Lost/5xx/malformed mutation responses remain
  unknown and block immediate replay; refresh the relevant records and reconcile the original
  operation before deciding what to do. This is an in-memory UI guard, not durable idempotency
  across reloads/tabs. C11/C12 server identities and claims remain authoritative.
- Cancelling the approval-comment prompt sends nothing. Approval responses show their actual
  status: approved/pending confirmation, executing, executed, failed, unknown, compensated,
  compensation failed, rejected or expired. Only `executed` is displayed as execution success.
- SSE has a five-minute request deadline, 2 MiB total bytes and a 256 Ki-character parser
  buffer limit. JSON events may span chunks and use LF/CRLF. Final/cancelled/error is required;
  premature EOF, malformed/unknown events, session mismatch or duplicate terminal events
  produce an incomplete answer with a warning. Partial text is preserved but cannot receive
  feedback as a completed answer. New-session/history controls are disabled while streaming.
- A successful cancel request means only signal acceptance. Keep reading until a server
  terminal event; neither network abort nor the cancel button claims business rollback.
- Failed lists clear stale rows and show unavailable, distinct from a confirmed empty list.
  Documents never fall back to seeded records. System status is labelled observations;
  C21 must separately fix readiness and auditing.

## API-only administration procedure

These are acceptance instructions, **not executed results**. Use a disposable, authorized
reference environment with synthetic users/documents. Authenticate through the application
and use an approved same-origin API client or `/docs` with an in-memory bearer token. Never
put credentials in URLs, shell arguments, screenshots, committed files or exported HARs.
The prefix below is `/api/v1/admin`; the OpenAPI schema is the exact request contract.

1. Users: `GET /users?limit=...&offset=...`; `POST /users` with a unique synthetic `username`,
   one of the five roles, approved `department`, optional synthetic email and an externally
   supplied `initial_password` (8–72 characters). Record the returned ID, not the password.
   `PATCH /users/{user_id}` changes `role`, `department` or `is_active`; repeat GET and login.
   Test disabling a synthetic logged-in account and changing its role/department, then verify
   the old token cannot retain authority. Use another authorized admin for recovery; no deletes.
2. Knowledge: list `GET /knowledge-candidates`; select a known fixture and either
   `POST /knowledge-candidates/{id}/approve` with `doc_type`/`dept_namespace` or
   `POST /knowledge-candidates/{id}/reject` with nonempty `reject_reason`. An approve 202 is
   **queued only**: retain `task_id`, query `GET /task-jobs/{task_id}`, then
   `GET /documents/{id}/publications` and `GET /documents`. Require publication/visibility
   evidence and authorized retrieval before claiming published (C15).
3. Failed knowledge tasks may use `POST /task-jobs/{task_id}/retry-knowledge` only after
   reconciliation under the C15 contract. `POST /documents/{id}/deactivate` is retained
   deactivation; verify ledger/publication state and retrieval invisibility. It is not deletion.
4. Repeat direct requests with each non-admin role and foreign IDs: require denial with no
   mutation, not just a hidden tab. Record status and sanitized IDs. Keep all fixtures retained;
   historical reset SQL in older manuals is not part of these procedures.

## Frozen browser matrix: browser-delivery-v1

All rows start **BLOCKED**. Execute through the delivered Linux image/Nginx URL, not a
standalone HTML copy. Desktop Chromium and Firefox are first acceptance targets; record
their actual versions and OS (none is certified yet). Other engines/mobile remain unverified.
Run identity/negative controls for all five roles; expand each row into separately recorded
subcases. A row passes only when every required subcase passes on both target browsers.

| ID | Steps and required observations | Status |
| --- | --- | --- |
| B01 | Load `/ui/` with public CDN access unavailable; confirm all three JS paths are same-origin, exact bytes/SRI, no external script requests. In separate fault fixtures, block Vue and sanitizer; observe static failure or escaped text, never uncompiled controls/raw HTML. | BLOCKED |
| B02 | Log in/out with each provisioned role; reject bad password, disabled user and failed/malformed `/me`. Picker/handoff claims never grant access. Verify fresh `/me` before workspace and cleared password. | BLOCKED |
| B03 | Run C19 S01–S16 through the browser, including replay, rotation, disabled mapping and IdP outage. Check one-shot handoff removal, memory-only token and relogin on refresh. This row cannot replace any S case. | BLOCKED |
| B04 | Delay login/list/history/stream replies; logout and log in as another user. Verify no previous identity, protected rows, message or error changes the new session. Test simultaneous role/department change and token expiry. | BLOCKED |
| B05 | Each role submits permitted chat, receives progress/token/final and correct citations/metadata; verify final answer replaces partial text. Disallowed actions have no side effect. Cross-check C17/C18 evidence, not prose alone. | BLOCKED |
| B06 | Request cancellation before/after session ID and during work; repeated click sends once. Accepted signal is not stopped/rolled back. Require confirmed cancellation or final result; cancellation service failure remains visible. | BLOCKED |
| B07 | Interrupt network/proxy midstream, exceed deadline, inject malformed/wrong-session/duplicate terminal events. Preserve partial text as incomplete, never success/cancelled. Confirm reconnect does not auto-repeat a business action. | BLOCKED |
| B08 | Load owned history after completion; foreign/missing history denied or unavailable. Start a new conversation during delayed history and verify isolation. During streaming history/new-session controls stay disabled. Refresh requires login. | BLOCKED |
| B09 | Originator creates an authorized high-risk request. Manager/admin approves or rejects appropriate rows; cancel comment prompt sends nothing; repeated click and two-browser races have one server transition. Verify denied foreign/expired/already claimed rows. | BLOCKED |
| B10 | Originator resumes approved_pending_reauth; verify current permission, expiry and ownership. Observe executing/executed/failed/unknown/compensated/compensation_failed separately with persisted evidence. Lost acknowledgement never becomes success or automatic retry. | BLOCKED |
| B11 | Manager/admin creates draft, activates it and changes traffic; verify returned contract and list state, invalid inputs and duplicate/outage handling. All other roles have hidden controls and server denial on direct writes/reads. | BLOCKED |
| B12 | Admin document ledger shows actual published records. Empty/403/timeout/malformed/5xx produce distinct appropriate states and no seeded/stale fallback. Other roles cannot load ledger. Synthetic business tabs remain explicitly labelled. | BLOCKED |
| B13 | Execute API-only user and knowledge procedures above, including all non-admin negative controls, 202-to-worker-to-publication evidence, deactivation and old-token denial. No UI page is presumed present. | BLOCKED |
| B14 | Render hostile Markdown/HTML, links, event attributes and encoded payloads with actual bundled parser/sanitizer and browser DOM; no script execution or credential exposure. Repeat missing/throwing sanitizer case and inspect safe fallback. | BLOCKED |
| B15 | Check navigation, focus/keyboard controls, readable loading/empty/error messages and layout at desktop and narrow viewport on both target browsers. Feedback submits once; failure/incomplete/cancelled answers never falsely show received. Record accessibility/layout failures. | BLOCKED |
| B16 | Build and scan final candidate image, verify manifest inside it and Nginx `/ui/`, MIME/SRI/TLS/cache behavior; inspect redacted network/storage evidence for tokens/private data. Confirm component observations do not imply C21 readiness. | BLOCKED |

## Evidence and remaining gates

Use the [engineering evidence template](../40-process/模板-工程验收证据.md). For each subcase
retain candidate commit/image digest, asset-manifest SHA-256, run ID, actual timestamp,
browser/OS versions, synthetic role/record IDs, exact steps, expected/actual result,
PASS/FAIL/BLOCKED and redacted screenshots/network status plus independent server evidence.
Do not export raw bearer tokens, cookies, passwords, response bodies with private data or HARs.
Record missing evidence as BLOCKED; failed behavior as FAIL. A generated checklist is not evidence.

No browser, application, TLS, real JWT/PG/Redis/Milvus/LangGraph/API/SSE, Docker or paid model
was executed here. Review the existing audit-cache filesystem deletion before any application
launch under the no-deletion policy; its non-deleting replay belongs to C21. C10 lease-expiry
writing is still unresolved. S01–S16, R01–R20, full RAG and earlier real runtime/historical
credential gates stay BLOCKED. Full pytest, strict OpenSpec CLI and image/advisory scans were
not run. Reference browser success would still not accept enterprise SSO/UAT or production.
`formal_uat=false`, `release_evidence=false`, `release_allowed=false`.
