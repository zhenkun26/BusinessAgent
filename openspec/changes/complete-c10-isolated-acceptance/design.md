# Design
## Normative mapping
- checkpoint-durability.md:209-220 defines installed compatibility, both-backend restart, Redis TTL, outages, provisioning and API/browser requirements.
- checkpoint-durability.md:228-248 defines eleven stale-writer scenario rows.
- engineering-delivery-closeout/tasks.md:52 requires isolated Linux execution.
## Phase A identifiers
C10-PG-BASE: 17 independently checked PG saver/publication assertions.
C10-REDIS-BASE: the same 17 assertions on actual Redis Search/JSON saver.
C10-PG-FAULT: 24 checks including SIGSTOP immediately before aput/aput_writes SQL, natural lease expiry and real COMMIT response loss.
C10-PG-RESTART: five snapshot comparison assertions after a controlled fixture restart.
These numbers are execution completeness guards, not a substitute for the normative matrix. Redis-only/PG-only expiry, lock-boundary interleavings, full outage/lifecycle, Redis retention/restart, API/JWT/SSE/browser and backup/upgrade remain BLOCKED until separately evidenced.
## Isolation and evidence
Official pinned Linux amd64 PG/Redis Stack fixtures; loopback random ports and unique names/volumes. Synthetic credentials only, no production secrets, no privileged mode or socket mount. No rm/prune or filesystem deletion. Stop owned fixtures and retain data. Strict fixture labels/IDs bind restarts.
Harness reports commit/tree/source hashes and backend/library/schema identities. Raw logs/config stay local; CI uploads only whitelisted JSON. Missing, skipped, duplicate or failed declared phase cases fail the phase job. full_c10_acceptance is always false while normative gaps remain.
## Limits
Synthetic direct saver workers do not prove actual graph/model writes, HTTP/SSE or UAT. macOS driver execution is supplementary even when stores are Linux containers. CI phase success does not clear full runtime/RAG/rights/release gates.

## First-stage adjustment
The owner subsequently selected open-source usability first, rather than full enterprise acceptance. Phase A remains a reproducible synthetic persistence slice. All remaining normative rows stay BLOCKED, including two distinct expiry directions, all late callback combinations, row-lock/commit takeover, missing exact IDs/backend mismatch, startup v7/drift refusal and matching-backup restore. Do not expand the merge criterion to claim these later stages completed.
