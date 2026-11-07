# Keyboard, control names and status messages (F2-07)

## Plan recorded before implementation — 2026-10-20

Parent: `182c252`. This increment covers the existing same-origin single-page UI. Keep
current Chinese product copy and identity/authorization, mutation and streaming contracts.
No dependencies, new framework, service/model calls, upload or remote action. Real browser,
assistive technology, layout/contrast, runtime and full RAG acceptance remain BLOCKED;
F2-05 privacy and F2-09 sources pending, C10 OPEN.

### Implementation sequence

1. Convert click-only account choices, manual-login entry, navigation, logout, suggestions
   and scene actions to native buttons. Use ordinary disclosure groups with Tab/Shift+Tab,
   Enter/Space activation, Escape dismissal and exposed expanded/current state. Do not add
   ARIA menu/tab roles whose composite keyboard contracts are not implemented.
2. Associate login, chat and dynamic prompt inputs with labels and helpful instructions;
   give feedback and repeated row/refresh actions contextual names. Provide visible focus.
   Native form submission handles password Enter. Guard chat Enter against composition,
   keyCode 229, repeats and modifiers; preserve Shift+Enter and input-method editing.
3. Focus newly exposed manual input, selected-account password, activated page heading,
   draft filled by a scene/reference action, and login/logout targets after rendering.
   On send focus the pending status; on terminal restore the composer only while focus
   still belongs to that request's chat controls and the identity/session/view is current.
   Never move focus for each token or steal it from another view/control.
4. Make login errors, toast notifications, loading/empty/error states and chat lifecycle
   discoverable. Chat announcements use fixed start/cancel/validated-terminal summaries,
   without answer/token text or the per-second timer. The transcript is a named keyboard
   scroll region, outside live regions. Completion is announced only after stream validation.
5. Extend the existing Node VM/static suite with synthetic event/focus/HTTP doubles and
   source-semantic checks. Use the retained Vue compiler for syntax where feasible, without
   claiming DOM or screen-reader behavior. Run existing browser credential/asset checks and
   appropriate Python regressions. Refresh only affected pending-source hashes.
6. Review source/diff/docs, update existing trackers and OpenSpec, then commit locally only
   and wait. No push/upload, merge, release, deployment, main-spec sync or archive.

### Offline exit criteria

| Area | Required evidence |
| --- | --- |
| Keyboard entry points | Former click-only actions have native semantics, visible focus and meaningful expanded/current state; disclosure Escape restores its trigger |
| Forms and names | Every existing input/textarea has an associated label or contextual accessible name; repeated feedback/record/refresh controls identify their target |
| Composition | IME/composition/229/repeat/modifier events do not submit; plain Enter submits once and Shift+Enter is left to the browser |
| Focus ownership | Intentional navigation/selection restores valid targets after rendering; stale identity/session callbacks and terminal results do not steal focus |
| Status truth | No token/timer live announcements; cancellation receipt remains requested, errors/EOF remain incomplete, completion waits for validated terminal/stream end |
| Regressions | Existing role/auth/duplicate-write/SSE/sanitization contracts continue passing; source inventory retains all pending rights |
| Acceptance boundary | VM/static/compile checks are offline evidence only; F2-07 and B01–B16 remain OPEN/BLOCKED for actual browser/assistive-technology evidence |

## Implementation and verification

The plan above preceded implementation. The existing page now uses native buttons for
account choices, manual-login entry, primary/reference navigation, logout, suggestions
and scene choices. These are ordinary disclosure groups and navigation buttons; Tab and
Shift+Tab use native order, Enter/Space use native activation, Escape closes an open group
and restores its trigger. There is no modal trap or custom menu/tab keyboard protocol.
The former pointer mask is replaced with outside-click dismissal. Native login form
submission handles password Enter; all other form buttons have explicit action types.

Login/chat/prompt fields have labels and descriptions. Dynamic prompt IDs encode the
prompt name; weight labels include the version. Feedback, record query, approval, refresh
and prompt mutation buttons identify their target. `:focus-visible` adds an outline;
headings accept programmatic focus without positive tab indexes. This does not measure
contrast, wrapping or focus visibility/clipping in any browser.

`onDraftKeydown` submits plain Enter once. It leaves composition state, `isComposing`,
legacy keyCode 229, repeat, already-handled events and modified Enter to editing. Explicit
composition-start/end bindings complement the event flags; actual IME ordering remains
unverified on each target browser/OS. Buttons still use the existing submit/action guards.

Focus moves after Vue rendering to intentional targets: manual username, selected-account
password, new page heading, inserted draft, post-login composer and logout field. Request
start focuses a named pending status. After validated termination, restoration occurs only
if the active element still belongs to the pending/cancel controls in the current chat.
Approval/confirmation refresh can restore its page heading if its original control lost
focus to the document body. Render callbacks compare identity, conversation generation,
view and active element; the document body is an allowed fallback for removed/disabled
controls. This source-level policy cannot prove browser focus behavior, and body focus
cannot distinguish every deliberate document interaction.

Toast notifications use a persistent polite live region. Login errors use an alert;
approval and existing list states have status semantics. Chat lifecycle uses a separate
persistent polite atomic region with fixed start/completed/cancelled/incomplete summaries.
The transcript is a named focusable scroll region outside live regions. Per-token content,
progress nodes and elapsed seconds are not live announcements. Cancellation receipt uses
the existing “requested, wait for server terminal” notification; completion waits for a
validated terminal, EOF and clean remaining buffer. Malformed/duplicate/failed endings
remain incomplete. Announcements neither repeat answer text nor imply business execution.

### Offline evidence — 2026-10-20

- PASS: **21 new Node VM/compile cases**, existing page suite **69 cases** total. These
  execute real inline methods with synthetic key/focus/HTTP doubles; deferred stream and
  render cases cover stale identity/session/view/focus, final-before-EOF, cancellation,
  malformed events and incomplete outcomes. No native DOM/event dispatch is exercised.
- PASS: **8 new Python source tests + 46 subtests** check native handlers, associated
  labels, disclosure targets, composition bindings, status/transcript separation, contextual
  names, duplicate attributes and focus targets. The parser sees source attributes, not the
  browser accessibility tree or final computed accessible names.
- PASS: full local pytest **1183 tests + 484 subtests**, zero skips/xfails/guard denials;
  45 existing dependency warnings. Installed declared production versions matched and tested
  source stayed stable. Python coverage remains a backend regression measure, not JS coverage.
- PASS: all **14** existing browser credential/sanitizer VM cases after adding Vue's
  `$nextTick`/`$refs` to the old fixture; all **seven** retained distribution/license assets
  verify. No vendor/dependency update was required.
- PASS: actual retained Vue template compiler accepts the complete page template. The VM
  provides a rejecting/no-entity decoder because current markup contains no character
  references; future encoded entities require an explicit decoder update. Compilation does
  not mount the page or verify rendering/event behavior.
- PASS: pending-source integrity now **437 records**; safe_validate execution PASS with
  overall BLOCKED (exit 2); diff/source/link/manual OpenSpec structure review PASS.
  Strict OpenSpec CLI is unavailable / BLOCKED.
- Retained ignored local evidence: `enterprise-agent/eval/results/ci-pytest-273ec4c1502d41a980cfd93a85a0e6f0/`
  includes runner/test/source receipts, Node outputs and final commit binding. Nothing is
  uploaded. No current remote CI, browser or production-readiness claim is made.

Read-only entries from the repository root:

```bash
node enterprise-agent/tests/test_browser_delivery.cjs
node enterprise-agent/tests/test_browser_credential_safety.cjs
python3 -I -B enterprise-agent/tests/test_keyboard_accessibility.py
python3 -I -B enterprise-agent/scripts/verify_frontend_assets.py enterprise-agent/app/static
```

The Node entries only read local source/assets and execute VM doubles; the Python entry
only parses local source. They do not start a browser/server, install packages, write files,
delete files or call real APIs. Full pytest uses the retained no-network/no-deletion runner;
it is a separate diagnostic process, not a startup or acceptance command.

### Required browser acceptance — NOT EXECUTED / BLOCKED

Use the existing [B01–B16 procedure and evidence fields](browser-delivery.md), expanding B15
with the steps below in an authorized isolated synthetic environment. Record exact commit,
image/served HTML hash, browser/OS/IME and assistive-technology versions, expected/actual
behavior, redacted evidence and PASS/FAIL/BLOCKED for every role/target combination. No
browser, screen reader, customer data or real model was used in this increment.

| B15 subcase | Required observations | Current status |
| --- | --- | --- |
| Login and logout | Tab/Shift+Tab reach account/manual/password/local-login/SSO; Enter/Space activate expected buttons, Escape dismisses account choices; rejected credentials are announced; success/logout focuses the intended field | BLOCKED |
| Composition and conversation | Chinese IME candidate Enter never sends; plain Enter sends once, Shift+Enter inserts a newline; transcript scroll works from keyboard; send/cancel/final/failure focus and status are accurate | BLOCKED |
| Scene and reference | All choices are keyboard reachable, Escape/outside dismissal works, selection fills/focuses draft, no trap or hidden-control stop; main navigation exposes current page | BLOCKED |
| Approval and prompt roles | Manager/admin approve/reject/confirm via keyboard and native comment prompt; cancelled prompt submits nothing; refreshed rows restore sensible focus; dynamic input/button names identify the right record/version; ordinary roles stay restricted | BLOCKED |
| Reader and async ownership | Screen reader announces loading/error/requested/validated end without token/timer flooding; user focus on another control/view survives delayed replies, logout and role change | BLOCKED |
| Layout and visibility | Desktop/narrow viewport, 200% zoom, focus outline/clipping, high-contrast mode and foreground/background contrast measured with actual tools; record failures | BLOCKED |

C20/F2-07 remain OPEN. Real browser/reader/layout/contrast, runtime and full RAG remain
BLOCKED; F2-05 private-data/provider/telemetry acceptance and F2-09 source rights are pending;
C10 stays OPEN. Source/VM success does not close B01–B16. Local review and commit only,
then wait; no push/upload, merge, deployment, release, main-spec sync, archive or next item.
