# Retained backup, recovery and rollback candidate (C22)

C22 is an **offline candidate**, not an accepted disaster-recovery system. D01–D16 below
remain **BLOCKED**, as do O01–O16/B01–B16/S01–S16/R01–R20, real runtime/full RAG and
historical credential handling. C10 lease-expiry writing remains open. See the
[delivery baseline](engineering-delivery-baseline.md), [C22 oracle](../40-process/ISSUES.md#c22)
and [delivery record](../40-process/阶段性总结_C22当前版本备份恢复与回退.md).

## Supported approach and retained assets

The controller `enterprise-agent/scripts/recovery.py` plans cold, whole-volume snapshots
for the single-host Linux Compose candidate. The helper `recovery_archive.py` is packaged
into the application image; it uses only the standard library. No dependency was added.
The old `backup.sh` is now a compatibility wrapper requiring the same explicit arguments;
its live tar, implicit defaults and automatic rotation/deletion are gone.

PostgreSQL is copied as a complete **stopped physical cluster**, including its WAL, not as
a partial table copy or logical SQL dump. The same stopped capture covers etcd, MinIO and
Milvus local state, Redis, shared audit and every other project named volume. Optional
CRM/ticket/mail, IdP, monitor/receiver and monitoring volumes are included when present.
Cold capture avoids asserting consistency for tar taken while databases are writing.
Whole-cluster shutdown/copy requirements follow the [PostgreSQL 16 documentation](https://www.postgresql.org/docs/16/backup-file.html).
This does not prove cross-service business consistency: external effects and in-flight
operations must be drained/reconciled, and D06/D07/D09 remain mandatory.

The source must have expected core service mounts, Compose-labelled local named volumes,
no driver options, no anonymous/external or unmapped orphan state volumes, no writable bind
mounts, and no
unknown outside container attached as a writer. Read-only config mounts are recorded only
by target/type, not copied. Container writable layers, process memory, registry images,
host files, TLS/private keys and environment secrets are **not** backup contents. Retain
reviewed config hashes, secret-version references and exact image IDs/digests separately.
Do not read/export raw secrets into a plan, commit, terminal log or evidence report.

No NFS, multi-host, hot backup, PITR, tablespace links, incremental backup, ACL/xattr/SELinux
metadata, sparse-file preservation or cross-version database restore is claimed. Filesystem
entries must be regular files/directories; links, special files and special mode bits are
refused. Unsupported state requires a reviewed extension, not silently skipped files.
Numeric UID/GID, basic mode, names, sizes and SHA-256 content are retained/read back; file
timestamps are not a recovery oracle. Limits are 64 project containers, 128 volumes, 512
host containers, two million entries and 4 TiB logical bytes per archive, and 256 MiB per
member manifest. These are safety ceilings, not tested capacity or completion guarantees.

Backups contain private database/Redis/IdP contents despite safe terminal output. Bundle
and receipt directories are new, mode 0700; metadata/archive files are 0600. Provision
an encrypted, access-controlled disk and an independently secured offline/off-host copy
before real acceptance. Encryption, key escrow and copy transport are not implemented
or validated by this tool. No rotation, purge, container removal or volume removal occurs;
all helpers, failed bundles and partially restored volumes remain for the user.

## Planning and explicit execution boundary

The commands here are instructions for a later **authorized isolated Linux environment**;
none was executed against Docker, databases or services during C22. Python 3.11+, Docker,
matching image/architecture and the source's exact reviewed configuration are required.
Use absolute paths without symlink components; bundle parents must already exist. The
source Docker context must be the intended isolated host. Exclude external operators,
automation and host-level volume writers throughout the maintenance window.

From `enterprise-agent/`, gather the sanitized inventory and create a fresh plan:

```bash
python3 -I -B scripts/recovery.py inventory --project c22-source --output /secure/recovery/inventory-01.json
python3 -I -B scripts/recovery.py plan-backup --inventory /secure/recovery/inventory-01.json --helper-image registry.example.invalid/businessagent@sha256:REVIEWED_DIGEST --commit REVIEWED_40_CHARACTER_COMMIT --output /secure/recovery/backup-plan-01.json
```

`inventory` is a read-only Docker observation; the other command only reads the inventory
and current schema manifest and writes a new plan. Placeholder commands are not executable
configuration. Review the exact source IDs/states/mounts, helper image, commit, schema hash,
limits, outage window and asset security. Planning prints the canonical plan SHA-256. It
is a review binding, not a signature or authorization service. CLI output is fixed codes/
summary hashes; raw Docker errors and environment values are suppressed.

Only after separate execution approval, bind the exact plan digest and source project:

```bash
python3 -I -B scripts/recovery.py backup --plan /secure/recovery/backup-plan-01.json --approved-plan-sha256 REVIEWED_PLAN_SHA256 --isolated-project c22-source --execute --output /secure/recovery/bundle-01
```

Without `--execute` and the matching digest/project, no mutation is attempted. Execution
rechecks source identity and schema, requires an already-present helper image with the
same image ID as API/api2/worker, and refuses existing output. The helper rechecks its
packaged schema manifest too. The manifest hash is an artifact identity; it is not proof
that the source database actually has that schema. D06 must verify the actual ledger.

Originally running containers stop in dependency order, application writers first. Every
source container must then be stopped, not paused/restarting, with exit code zero. Nonzero
shutdown is refused rather than labelled a clean snapshot. Check the full inventory before
and after each volume copy. A concurrent restart invalidates capture. Stopped-state sampling
cannot fence an external host writer or an operator racing between observations; isolation
is a required prerequisite, and this does not solve C10.

Helpers have no network, a read-only container root, a read-only source volume and only
the new bundle writable. They run as container root with CHOWN/FOWNER/DAC_OVERRIDE to
read private database files and preserve numeric ownership, not as privileged containers.
The root helper and exact host bind scope require review before real execution. No image
pull or application startup occurs implicitly. Docker stop/start and database shutdown
may trigger their own internal file lifecycle; source review alone does not establish
compliance with the non-deletion boundary. D16 remains BLOCKED pending filesystem review.

Each volume produces `<source-volume>.tar` and `<source-volume>.json`; the latter has all
member metadata/content hashes and the tar hash. `plan.json` and `result.json` bind them.
The complete marker is written only after every archive is verified. A failure retains
partial output, never creates a usable complete bundle from partial data. SIGTERM is
cooperative; SIGINT/copy/stop failures attempt independent resumption of every originally
running container, even when one restart fails. Originally stopped containers stay stopped.
`source_resume_failed=[]` observes immediate process state, **not** readiness or lasting recovery.

If the controller/host is killed before its recovery block, retain the original plan and
use its explicit resume path after inspecting the target:

```bash
python3 -I -B scripts/recovery.py resume --plan /secure/recovery/backup-plan-01.json --approved-plan-sha256 REVIEWED_PLAN_SHA256 --isolated-project c22-source --execute --output /secure/recovery/resume-observation-02.json
```

The original container/mount identities must still match. There is no infinite retry.
Inspect every recorded failure and recheck `/ready` and actual consumers; do not conclude
success from a process restart. Helper timeout attempts to stop that helper; failed stop/
RPC acknowledgement remains uncertain. Inspect retained helper state before further work.
Never reuse a partial bundle, receipt directory or existing target volume to resume copying.

## Fresh-volume restoration and activation

The controller validates the complete bundle, all hashes, member paths/types/parents,
unique entries and schema identity **before creating any target volume**. Restore is
only allowed into a distinct project named `c22-restore-*` with no existing containers or
matching volumes. Created volumes receive this attempt's label; ownership and attachment
checks reject a precreation race before writing. Docker otherwise reuses existing names,
as documented in [docker volume create](https://docs.docker.com/reference/cli/docker/volume/create/).
This guard does not replace exclusion of concurrent Docker administrators.

```bash
python3 -I -B scripts/recovery.py plan-restore --bundle /secure/recovery/bundle-01 --project c22-restore-01 --output /secure/recovery/restore-plan-01.json
python3 -I -B scripts/recovery.py restore --plan /secure/recovery/restore-plan-01.json --approved-plan-sha256 REVIEWED_RESTORE_PLAN_SHA256 --isolated-project c22-restore-01 --execute --bundle /secure/recovery/bundle-01 --output /secure/recovery/restore-receipt-01
```

Tar extraction does not use `extractall`: it validates all members first and opens files
exclusively in empty new volumes, refuses links/traversal/duplicates, restores owner/mode
and compares full content inventory. This addresses only the explicitly supported format;
[Python's tar guidance](https://docs.python.org/3/library/tarfile.html#extraction-filters)
also explains why archives and partially extracted output require care.

The result directory retains a source-bound restore plan, result and
`restored-volumes.compose.json`. This generated Compose overlay maps **every captured
logical volume** to the exact restored external volume. A stopped C22-labelled restore
helper is permitted as a retained attachment; a running helper/unknown writer blocks a
future capture. Do not restart old helpers or use their names for a new attempt.

Byte restore never starts API, worker, database, IdP or reference services. Before any
activation, prepare the exact source service image IDs/platforms and config/secret versions;
base Compose tags alone are insufficient. Review a resolved Compose model that combines
`docker-compose.prod.yml`, the source's original reference/SSO/observability overlays,
`deploy/docker-compose.dr-drill.yml` and the generated external-volume mapping. Use the
new project name. Verify every service mount resolves to the receipt's restored volumes,
never source or empty automatically created volumes; keep all ports/networks isolated.
Do not print resolved environment secrets or run `up` without an explicit service list.

Start only isolated stores and required reference services first. Keep API/worker profiles
disabled until the following independent evidence is complete:

1. PostgreSQL schema ledger 1–7, checksums, users/roles, prompts, approvals/execution IDs,
   tool-operation receipts, jobs/leases, Saga runs/steps, document publication generations
   and audit IDs: compare exact record counts plus canonical content hashes to a trusted
   source oracle captured at the same quiescent point. Read-only SQL must use a transaction;
   retain hashes/counts, not raw user payload. A stale pre-stop export is insufficient.
2. Milvus: load the actual restored collection, compare entity/chunk generation identities,
   perform deterministic known-vector reads and actual authorized retrieval. Counts alone
   do not prove MinIO segment objects or index readability. Re-run the frozen C17/C15/RAG
   procedures on a separately approved runtime candidate; model calls require authorization.
3. Redis/checkpoints, audit pending/acknowledged events, optional reference ledgers/receipts,
   IdP codes and monitor condition/receipts: account for wall-clock expiry and source timing.
   Do not treat restored sessions, used authorization codes or expired leases as newly valid.
4. Reconcile every pending/unknown external operation against independent receiver evidence.
   A restored pre-dispatch record does not prove the external effect never happened. Keep
   outbound traffic blocked and worker stopped until reviewed reconciliation. No automatic
   queue replay or copied SSO/session reactivation is authorized by this tool.
5. Then verify actual roles/login/SSO, business read/write/approval/recovery, `/ready`, all
   consumers, audit replay, metrics and alert receipt under the approved isolated profile.
   This may expose prior C10 or other failures; mark FAIL/BLOCKED, never silently waive them.

The controller does not create the database/vector semantic oracle or grant acceptance to
operator assertions. D06–D10 must retain independently reproducible query procedures and
results, not only the byte inventories. This remains a real-execution gap, not completed work.

## RTO, RPO, cadence and rollback

Target RTO is <=1 hour; target RPO is <=24 hours. Record incident start through **verified
application/business recovery**, including provisioning, validation and reconciliation.
Extraction duration is not RTO. Use snapshot quiescence-start time as the conservative
recovery-point bound; a newer file modification time is not a recovery point. Require
snapshot-start <= snapshot-finish <= incident <= service-verified with explicit time zones.

Proposed cadence is **every 12 hours**, with monitored snapshot age, independently retained
copies and an approved cold-maintenance window. It is not scheduled or enabled. Alert and
escalate before age reaches 24 hours; a failed/missed capture leaves the previous age growing.
Daily schedule text alone cannot establish RPO, particularly while a new cold copy is still
in progress. If repeated outages are unacceptable, review a hot-backup design separately;
this candidate makes no availability promise.

`assess-window --inventory /secure/recovery/timestamps.json --output /secure/recovery/window-01.json`
accepts ISO timestamps named `snapshot_started_at`, `snapshot_finished_at`, `incident_at`,
`service_verified_at`. It calculates durations and reports OBSERVED or FAIL. It always keeps
runtime acceptance BLOCKED: it cannot authenticate timestamps or business recovery evidence.

Image-only rollback planning uses `plan-rollback --inventory /secure/recovery/old-candidate.json
--output /secure/recovery/rollback-plan-01.json`; input fields are immutable `image`, 40-character
`commit` and `schema_sha256`. Equal schema is necessary, not semantic compatibility: the plan
still reports `execution_allowed=false`. Re-test an old image in a cloned target before
manual traffic switching. Replacing current containers can interrupt requests and is not
performed by this tool.

A different schema manifest is rejected: no down migration or older application on newer
state. A full older-snapshot rollback needs its matching reviewed tool/image/schema on a
**separate new target**, deliberate data-loss assessment since the recovery point, and external
ledger reconciliation. Do not relabel an old manifest as current, drop a schema, overwrite a
source volume or replay a logical dump into live tables. Pre-C22 images without the archive
helper cannot be assumed usable as helper images. Incompatible historical recovery stays
BLOCKED pending a separate reviewed procedure.

## Frozen real acceptance matrix

All cases require the final commit/image digest, platform, exact non-secret config hashes,
source/target identities, retained asset hashes, UTC times, injected fault and restoration
steps, expected/actual result and independent semantic evidence. All are **BLOCKED** now.

| ID | PASS oracle | Status |
| --- | --- | --- |
| D01 | Inventory covers core plus enabled reference/IdP/audit/monitor state; missing/foreign/writable-bind/unsupported state refused | BLOCKED |
| D02 | Approved immutable candidate/schema/project match actual Linux source; altered plan, image, state or mounts refused before stop | BLOCKED |
| D03 | Clean quiescence stops all writers/stores; source images/platform retained; no external writer during every copy | BLOCKED |
| D04 | Stop/copy/space/timeout/SIGTERM failures resume every originally running service or emit explicit failures; stopped services stay stopped | BLOCKED |
| D05 | Controller/host interruption, manual resume and uncertain Docker acknowledgements recovered with retained evidence; no permanent silent pause | BLOCKED |
| D06 | PG full cluster starts with exact candidate; schema ledger, counts and quiescent canonical content hashes match | BLOCKED |
| D07 | etcd/MinIO/Milvus load actual collection, compare versions/entities and content/known-vector retrieval; no metadata-only false success | BLOCKED |
| D08 | Redis/checkpoint/audit/optional reference/IdP/monitor state restored with expiry, pending and receipt semantics accounted for | BLOCKED |
| D09 | Pending/unknown queue/Saga/approval/external effects independently reconciled before activation; no duplicate side effects | BLOCKED |
| D10 | Current roles, login/SSO, knowledge and approved business flow, consumers/ready/audit/alerts work on restored candidate; prior gates separately respected | BLOCKED |
| D11 | Existing target, altered member hash, traversal/link/special entry and target-creation race rejected with no existing-state overwrite | BLOCKED |
| D12 | Measured incident-to-verified-business RTO <=1h, including semantic checks; extraction-only result rejected | BLOCKED |
| D13 | Backup cadence actually enabled/observed under separate approval, newest complete snapshot age and independent copy establish RPO <=24h | BLOCKED |
| D14 | Equal-schema image rollback rehearsed on clone; incompatible schema rejected; full snapshot rollback assessed without source mutation | BLOCKED |
| D15 | Backup confidentiality/access/encryption/secret-version/image availability and numeric UID/GID/permissions validated on Linux | BLOCKED |
| D16 | Filesystem/Docker/process traces verify approved non-deleting lifecycle, retained failures/helpers/volumes and immutable source assets | BLOCKED |

Physical archive success does not close complete RAG or enterprise UAT. Failure remains
FAIL until corrected and rerun. C22/6.3 remain open; only its offline implementation can be
completed here. No push of C22, C23, deployment, release or OpenSpec archive is implied.
