# Design

Use the scanner's output option for pip-audit-report.txt, the path consumed
by the existing always-run artifact upload. Keep the project's exemptions
and scanner arguments. Exercise the step with an empty exemption list and a
populated list, on both successful and failed scans, using the runner's
default Linux shell.

Use the scanner's fix versions for certifi, langgraph-sdk,
langgraph-checkpoint-postgres, opentelemetry-api and pypdf. Keep the
OpenTelemetry SDK, semantic conventions and instrumentation on a compatible
release family. Resolve and install the complete production requirements in
an independent temporary environment, check package consistency, then rerun
the scanner against the updated requirements without any exemptions.

| Production package | Previous | Updated | Reason |
| --- | --- | --- | --- |
| certifi | 2026.7.22 | 2026.10.18 | PYSEC-2026-4320 |
| langgraph-sdk | 0.4.4 | 0.4.6 | CVE-2026-118667 |
| langgraph-checkpoint-postgres | 3.1.1 | 3.1.3 | CVE-2026-115883 |
| langgraph-checkpoint | 4.1.1 | 4.3.0 | Minimum required by the patched Postgres saver |
| pypdf | 6.19.0 | 6.21.4 | Highest fix version for the 18 PDF parser advisories in the baseline |
| opentelemetry-api and opentelemetry-sdk | 1.44.0 | 1.45.1 | CVE-2026-114603 in the API and the SDK's matching API requirement |
| opentelemetry-instrumentation, -instrumentation-asgi, -instrumentation-fastapi, -semantic-conventions and -util-http | 0.65b0 | 0.66b1 | Matching release family required by the SDK and FastAPI instrumentation |
