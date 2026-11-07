# Complete isolated C10 acceptance
## Why
The owner requested C10/runtime/RAG/UAT/source-rights acceptance before conditional merge. Existing live C10 evidence predates dependency updates and does not establish every required backend/API/Linux scenario.
## What changes
Add portable source-bound synthetic acceptance tooling and a dedicated Linux CI persistence job without weakening existing jobs. Preserve original scripts/data and record every unexecuted full-C10 requirement as BLOCKED.
## Scope
Phase A: actual PostgreSQL and Redis checkpoint round-trips across independent processes, active overlap and natural lease expiry, stale publications, real PG commit-ack loss, controlled PG restart. Further phases add Redis retention/restart, full lifecycle/outage, API/SSE and upgrade/recovery matrix evidence.
No deployment, source-rights clearance, real model/RAG or UAT acceptance is implied.
