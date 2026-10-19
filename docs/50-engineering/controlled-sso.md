# Controlled SSO reference profile

Status: C19 implementation/offline candidate; **all S01–S16 runtime cases BLOCKED**.
This project-controlled issuer is a synthetic integration fixture, not an enterprise IdP
or an OpenID certification claim. C18 R01–R20, full RAG, C10 fencing and C21 audit replay
remain unchanged. No real keys, credentials, users, images or runtime evidence are included.

## Implemented contract

The application starts at `GET /api/v1/auth/sso/login`. Redis retains a random state bound
to nonce and an S256 verifier for 600 seconds. A Secure/HttpOnly/SameSite=Lax cookie binds
the browser. The IdP accepts one exact registered client and HTTPS redirect, `code` flow,
`openid` scope and S256; no wildcard redirect or dynamically supplied key URL is accepted.
Its own browser request expires after 300 seconds and permits five failed password attempts.
The synthetic identities and distinct operator/client credentials come only from environment.

Successful authentication creates a 120-second code bound to the stored subject, client,
redirect, nonce and PKCE challenge. Only the code hash is stored. Token exchange checks
client credentials and verifier, signs RS256 and consumes the code in one SQLite writer
transaction. A lost response requires a new application login; token POST is never retried.
State is atomically consumed by Redis GETDEL before exchange, including provider-error
callbacks. Cookie mismatch does not consume another browser's state. There is no local fallback.

Application verification requires a fixed RS256 algorithm, a unique exact `kid`, a public
RSA signing key (2048–4096 bits, exponent 65537), and required `iss/sub/aud/iat/exp/nonce`.
It rejects embedded key headers, duplicate JSON keys, symmetric/private/weak JWKs, missing
or unknown keys, wrong issuer/nonce, invalid times and ambiguous multi-audience tokens.
Multi-audience tokens need matching `azp`; any supplied `azp` must match the client.
Clock tolerance is 30 seconds. JWKS is fetched for each callback; no stale-key fallback.
The configured HTTPS endpoints use verified CA chains, disabled redirects/environment proxies,
5-second HTTP operation timeouts, a 10-second total budget and a 64 KiB response limit.
Only a JWKS GET receiving 429/502/503/504 gets one immediate retry. Network failures return
a fixed unavailable result; token POST remains single-attempt.

The local identity is the exact `(issuer, sub)` pair. Subject is a nonempty string of at most
255 characters, never stripped, truncated or coerced; issuer is at most 512. Username/email
are display attributes, never account-linking authority. A first identity receives only
`salesperson` and the explicitly configured default department (`dept_sales` in this recipe).
Remote role/department claims cannot grant authority. Existing local role, department and
disabled state remain authoritative. Uniqueness conflicts reload only the exact identity;
other collisions fail closed and require review. SSO accounts receive an unknown random
password; even development passwordless mode cannot bypass their password check.

After verification the existing C06 escaped HTML handoff places the local JWT in one-use
sessionStorage, redirects to `/ui`, consumes it into memory and verifies `/me`. JSON clients
receive the normal token body. Tokens are never put in the redirect URL. Responses are
no-store/no-referrer; audit records contain a subject hash, not the raw subject. Real browser
storage, history, logs and HTML failure behavior still need S15 observation.

## Independent issuer and controls

`enterprise-agent/reference_idp/` has no application imports. `server.py` serves TLS on
8443 (authorize, authenticate, token, JWKS, discovery, health) and 8444 (operator only).
One replica owns one SQLite store. Initialization is explicit and refuses an existing store;
normal startup refuses a missing store, mismatched immutable identity or corrupt metadata.
Store identity binds its UUID, issuer/client/redirect, subjects and the pre-provisioned public
key ring. There is no startup reset, schema migration, cleanup or automatic key generation.

SQLite uses PERSIST journaling, FULL synchronization and in-memory temporary storage.
Requests, attempt counts, spent-code metadata and fixed-name events remain retained;
export omits raw state, nonce, code/hash, password, JWT, private key and browser cookie.
The protected database still contains request bindings and synthetic subjects. Physical
journal behavior, crash durability and filesystem retention have **not** been observed.
Evidence export stops with `evidence_limit` after 200 requests/codes or 1,000 events;
retain that store and use a separately provisioned fresh store for another run. Do not reset it.

Operator requests require the separate bearer credential on TLS port 8444, never exposed
through the browser gateway. Client credentials cannot authorize these routes:

| Route | Body / result |
| --- | --- |
| `GET /control/evidence` | Bounded store identity hash, published/active key IDs, request IDs/states, spent-code counts and fixed events |
| `POST /control/rotate` | `{"active_kid":"key-b","published":["key-a","key-b"]}`; selects only pre-provisioned keys and retains private key material |
| `POST /control/fault` | `{"request_id":"<known pending request ID>","mode":"<mode>"}`; immutable once, before form authentication |

Fault modes are `bad_signature`, `wrong_kid`, `malformed`, `issuer`, `audience`, `nonce`,
`expired`, `future_iat`, `missing_sub`, `long_sub`, `multi_audience`, `privilege_claims`.
Get the request ID from the synthetic login form or protected evidence response before
arming its fault; there is no unscoped "next request" injection. Faults are not enabled
on ordinary requests. Rotation events record occurrence, not old/new key lists; retain
operator before/after evidence snapshots for the complete timeline. Discovery advertises
only this profile. Access tokens are opaque unused artifacts; no userinfo, refresh token,
logout federation, dynamic registration, MFA, email delivery or production capacity claim.

## Approved dependencies and compatibility

The user approved dependency declarations and build import probes only: existing
PyJWT 2.15.0 gains `[crypto]`; cryptography 50.0.2, cffi 2.1.1 and pycparser 3.11 are pinned
in the production and independent IdP recipes. No local install/build/key generation ran.
Binary availability, resolution, `pip check`, image imports and security scans are pending.
`Dockerfile.idp` requires binary distributions and fails rather than silently adding a
compiler/Rust toolchain. Import probes do not test signature correctness.

Profile choices follow [PyJWT's fixed-algorithm guidance](https://pyjwt.readthedocs.io/en/latest/api.html),
its [crypto extra installation contract](https://pyjwt.readthedocs.io/en/2.10.0/installation.html),
[OIDC ID token validation](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)
and [OAuth PKCE guidance](https://www.rfc-editor.org/rfc/rfc9700.html).
Package metadata was checked at the public PyPI version endpoints; it is not an install or audit.

Existing HTTP SSO endpoints, permissive algorithm profiles and privileged default roles now
fail configuration checks. Old nonce-only in-flight state cannot complete a new callback:
restart login after rollout. Previously stored exact issuer/subject mappings are looked up
before new deterministic IDs are generated, so they retain IDs. Historical mappings created
by truncating/normalizing subjects require explicit operator investigation; no automatic
merge, rewrite or adoption is performed. A historical collision cannot be resolved from
current claims alone. Review those accounts before enabling this profile on existing data.
The legacy `SSO_DEPARTMENT_CLAIM` setting is retained for configuration compatibility but
no longer supplies local authority. No database migration is introduced.

## Isolated Linux recipe (not executed)

1. Use a new project/volumes and disposable synthetic identities. Resolve the C21 audit
   cache deletion/replay conflict before starting the application under the non-deletion
   policy. Review inherited service lifecycle/log retention too. This guide does not grant
   permission to run destructive scripts, cleanup, `--rm`, prune or delete volumes.
2. Build/review app and independent IdP images from the same candidate; record commit,
   immutable image digests, Python/packages, OS/architecture and security scan result.
   `Dockerfile.idp` and `Dockerfile.prod` are recipes, not built artifacts.
3. Populate ignored `.env.prod` per [deployment guide](../../enterprise-agent/deploy/DEPLOY.md)
   and `.env.sso` from [example](../../enterprise-agent/deploy/sso.env.example). Supply
   fresh UUID, distinct >=32-character client/operator credentials, 2–10 synthetic users
   (passwords >=16 characters) and 2–10 externally provisioned RSA signing keys in JSON.
   Provision the named local department and local admin using C03's reviewed procedure.
4. Externally provision a private CA and certificates in ignored `data/sso-tls/`:
   `ca.crt`; `gateway.crt/key` with SANs `app.reference.test`, `idp.reference.test`;
   `idp.crt/key` with SAN `reference-idp`. Configure certificate readability for container
   UID 65534 without making private keys public. Provisioning/permission changes are not
   automated. Mount only the CA into the API/worker, not private signing/TLS keys.
5. Use a dedicated browser profile that trusts this CA. Resolve both public names to the
   isolated host's loopback gateway (or a reviewed SSH tunnel), port 8443. Do not bypass
   certificate errors or use insecure HTTP. Keep the inherited 80/443 gateway disabled.
6. Merge `docker-compose.prod.yml` with `deploy/docker-compose.sso.yml`, using both env files
   and a fresh explicit project name. Validate with `config --quiet` in the target environment;
   do not print resolved configuration containing secrets. The SSO overlay provides an
   internal network, loopback-only TLS gateway and unexposed operator port. If also using
   C18's overlay, verify the final network lists preserve both `sso` and `reference` networks.
7. Initialize the IdP store once via its image command `python -B -m reference_idp.server
   --initialize`, in an explicitly named retained container with the recipe's env/mounts.
   Retain the initialization container and logs; no `--rm`. Review the fixed initialization
   marker, store UUID and identity hash, then start the normal command on the same volume.
   Initialization failure requires investigation of the retained store, not replacement.
8. Apply C03 migrations/bootstrap in the isolated app store, then start the normal API/worker
   and gateway after all preceding gates are addressed. No application module is launched
   as part of the offline verification entry. Record actual DNS/TLS, Nginx, browser/OS,
   Redis and PostgreSQL versions. `/health` alone cannot accept the SSO chain.

Operator control traffic uses the internal TLS endpoint with CA verification, secret-bearing
headers supplied in memory, and no verbose transcript. Do not put credentials in command-line
arguments, browser URLs or committed artifacts. Operator access to the isolated Docker host
is trusted; it is not an application-user privilege. No port 8444 is published to the host.

## Runtime acceptance matrix

Every row is **BLOCKED** until all listed subcases are actually observed. Record sanitized
steps, expected/actual results, timestamps, candidate/image/store identities, browser version
and hashes of retained artifacts. Record local user ID, role/department and disabled flag
from isolated PG and `/me` as well as IdP events; a redirect or token alone is insufficient.

| Case | Procedure and acceptance oracle |
| --- | --- |
| S01 | Start from `/ui`, choose SSO, authenticate synthetic user, complete callback/handoff and `/me`; repeat login returns the same local ID and no duplicate user. |
| S02 | Use two browser profiles/concurrent requests for one subject, then the second subject with the same display username; at most one local row per exact pair, distinct subjects never share an account; transient username conflicts may fail closed and require a fresh login. |
| S03 | Arm `privilege_claims`; first login is salesperson/dept_sales despite remote admin/finance claims. No remote attribute grants local authority. |
| S04 | With isolated administrator controls disable the mapped account; SSO and local password login deny. Existing locally assigned role/department remain unchanged on a later valid login; restore only by explicit admin action. |
| S05 | Separate pending requests for bad_signature/wrong_kid/malformed; no local user/JWT is created. Also verify algorithm substitution and duplicate/weak/private JWKS rejection in an isolated test proxy, not by weakening production settings. |
| S06 | issuer/audience/multi_audience faults deny; explicitly valid multi-audience+azp tokens require an additional controlled fixture/proxy and real signature validation. |
| S07 | nonce/missing_sub/long_sub faults deny; exact subject case/whitespace differences must never normalize into another mapping (additional synthetic fixture required). |
| S08 | expired/future_iat faults deny; wait for independent 120-second code, 300-second browser request and 600-second Redis state expiration. No synthetic clock evidence substitutes for actual expiry. |
| S09 | Missing/wrong cookie or state denies; replay and concurrent callbacks yield at most one success. IdP error consumes only the matching state. Retry starts a fresh login. |
| S10 | Controlled direct token requests test wrong client/secret/redirect/verifier, expired/spent code and concurrent redemption; bind positive token issuance to actual browser/app results. Redemptions never issue twice. |
| S11 | Start key-a; publish a+b, switch active to b, accept real b token; retain an unexpired a token for verification during overlap, retire a then prove it is rejected. Retain before/after operator evidence. Existing local JWT is a different token and is not a rotation oracle. |
| S12 | Stop/restrict IdP transport and test invalid CA, unreachable/malformed JWKS and response loss after code consumption. SSO fails closed; no token POST retry; ordinary local password login still accepts valid and rejects invalid/disabled credentials. |
| S13 | Route login and callback to different API processes sharing Redis, restart the first process and test Redis outage. Exactly one matching state is consumed, no process-local fallback. C10 write fencing is not covered. |
| S14 | Stop/restart the same IdP volume, test pending and consumed codes, key selection and identity checks; inject a crash around token commit and observe journal files. Physical persistence/retention must meet the non-deletion rule. |
| S15 | Inspect browser URL/history/storage before/after handoff, logout and failure; inspect sanitized app/gateway/IdP/audit logs and protected exports. No credential leakage, no reusable localStorage JWT. Do not save raw HAR/password/token dumps. |
| S16 | Verify separate operator/client access, unknown routes, duplicate headers/body limits, certificate hostname/CA checks and container isolation. Record real package/image scan results; operator evidence cannot attest the running image by itself. |

Faults not implemented by the bounded operator API (transport loss, malformed JWKS, crashes,
special valid claims) require a separately reviewed isolated proxy/fixture procedure. Their
subcases remain BLOCKED until that procedure and evidence exist. Never mark a partial row PASS.

`python -B -m reference_idp.acceptance` (from the backend directory) prints the complete
plan and exits 2 without network or writes. Optional `--observations <protected-json>`
validates at most 64 KiB of an operator report and still exits 2/status BLOCKED. Its schema is
exact: `candidate_commit` (40 hex), `app_digest`/`idp_digest` (`sha256:` + 64 hex), `store_id`
(canonical UUIDv4), `store_identity_hash` (64 hex), and all 16 `cases`. Each case has only
`id`, `reported_status` (PASS/FAIL/BLOCKED), `artifact_sha256` (up to 50 hashes; nonempty for
PASS/FAIL). Extra fields/free text are rejected. Reports never fetch/check source artifacts
or independently verify operator claims; every authoritative case remains BLOCKED pending
review of the actual retained evidence. Do not redirect over an existing record.

## Offline verification boundary

Reviewed command: `python3.13 -I -B enterprise-agent/eval/run_c19_controlled_sso.py`
from the repository root. It runs actual issuer/claim/state/mapping functions against
in-memory SQLite, transport/JWT/SQL/framework doubles, with an audit guard rejecting
network, disk database creation, writes/deletion and subprocesses. The signer is explicitly
non-cryptographic. Browser VM checks are also doubles. These results cannot prove RSA,
PyJWT backend loading, disk restart, PostgreSQL uniqueness or browser/TLS behavior.

See the [C19 delivery record](../40-process/阶段性总结_C19受控IdP与SSO完整链路.md).
All UAT/release flags remain false. C19 stays open; C20 and C19 push await confirmation.
