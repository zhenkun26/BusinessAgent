# Dependency remediation design

## Diagnosis

Trivy artifact 12093441066 from CI run 39011635217 reports:

| Package | Existing pin | Selected pin |
| --- | --- | --- |
| PyJWT | 2.13.0 | 2.15.0 |
| langgraph-sdk | 0.4.2 | 0.4.4 |
| pypdf | 6.15.0 | 6.19.0 |
| urllib3 | 2.7.0 | 2.8.0 |

PyJWT 2.14.0 would address the original HIGH/CRITICAL findings but its PyPI
metadata lists additional advisories fixed in 2.15.0. Select 2.15.0 rather than
introducing a known subsequent dependency-audit failure.

## Sources

- https://github.com/zhenkun26/BusinessAgent/actions/runs/39011635217
- https://pypi.org/pypi/PyJWT/2.15.0/json
- https://github.com/jpadilla/pyjwt/releases/tag/2.15.0
- https://pypi.org/pypi/langgraph-sdk/0.4.4/json
- https://github.com/py-pdf/pypdf/releases/tag/6.19.0
- https://github.com/urllib3/urllib3/releases/tag/2.8.0

All selected versions exist, are not yanked, and their queried PyPI metadata
reports no known advisories at inspection time. This metadata is preliminary
evidence; the project's CI audit and final image scan remain acceptance checks.

## Scope and compatibility

Keep exact production pins. Raise direct development floors for PyJWT and pypdf,
and make the security floors of existing transitive packages langgraph-sdk and
urllib3 explicit in pyproject.toml and requirements.txt. Do not change application
code, scanner severity, ignore-unfixed behavior, exemptions, or branch protection.

## Validation and delivery

Review all three dependency manifests and upstream runtime requirements.
Use the existing Python 3.11/3.13 CI matrix and production-image build/scan for
runtime verification. Existing tests exercise authentication, SSO, orchestration,
and external adapters. No redundant test that merely asserts version strings
is needed.

Local checks remain read-only because the default local interpreter is Python
3.9 and some existing tests remove temporary files. Remote CI is the established
validation path. OpenSpec CLI is unavailable; records are maintained manually
using the existing skip_specs convention, without claiming CLI validation.

Merge only the verified PR head. Required review approval is independent of CI;
do not represent an administrator merge as an approved review.
