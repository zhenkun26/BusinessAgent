# Isolated C10 persistence slice

This is a synthetic persistence demonstration, not full C10, model/RAG, enterprise UAT,
source-rights clearance or release approval. The complete unexecuted requirement list
is recorded as BLOCKED in report.json. It never authorizes production deployment.

## Requirements and execution
Use a disposable Linux amd64 environment with Docker, Git, Python 3.13 and the exact
packages from deploy/requirements-prod.txt (including a usable system libpq).
From the repository root, run:

    python -I -B enterprise-agent/eval/c10_live_acceptance/run.py --execute

The explicit execute option creates uniquely named PostgreSQL and Redis Stack containers,
retained volumes, random loopback-only ports and synthetic credentials. Official image
digests are pinned in run.py. It installs the application's managed schema and PG saver
schema only into the new synthetic database. Application children and nested workers use the newly created run directory as cwd,
reject any .env there, and receive only an allowlisted process environment plus explicit
fixture configuration. They never use the repository cwd or inherited provider secrets,
model profile or telemetry configuration. Existing application databases are not used. It stops only the containers it created; no rm/prune or data
cleanup is performed. Operators retain control of eventual cleanup.

Run configuration-isolation controls without starting any service:

    python -I -B enterprise-agent/eval/c10_live_acceptance/check_entry.py

This retains a synthetic .env trap and verifies both safe-cwd success and wrong-cwd
refusal through an audit hook. No real configuration file is read.

## Exact coverage
- PG saver independent-process overlap, expiry/takeover and publication checks: 17.
- Redis saver equivalent direct-store checks: 17.
- PG SIGSTOP scheduling before saver SQL and real commit-acknowledgement loss: 24.
- Controlled PG restart and exact snapshot comparison: 5.

The SIGSTOP injection is before SQL submission, not a claim of every server-side
interleaving. This is not complete graph, API/JWT/SSE/browser, Redis TTL/restart,
backup restoration or real-provider acceptance. Scope is intentionally narrow.

## Evidence and errors
Missing/failed declared cases, incomplete shutdown or dirty/changed source binding
produce nonzero exit. A fresh report.json under eval/results/c10-persistence-<id> is
the only upload-safe output. Other retained files include synthetic fixture credentials
and raw diagnostics and must not be published. CI uploads only that report.

The job uses synthetic data and performs no merge, registry publication or deployment.
