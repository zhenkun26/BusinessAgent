# Tasks

- [x] 1. Diagnose the failed image scan and verify upstream patched releases.
- [x] 2. Record the narrow remediation and validation plan.
- [x] 3. Update production pins and matching development dependency floors.
- [x] 4. Check manifests, upstream compatibility, and the scoped diff.
- [ ] 5. Push the fix and verify Python 3.11/3.13 CI plus image scanning.
- [ ] 6. Record validation and archive the completed repair.

## Delivery evidence

Initial failed run: 39011635217, head f612da9adb55204fc601e62c30b4c600e82450e4.
Python 3.11/3.13 jobs passed; Trivy reported 16 HIGH and 1 CRITICAL findings.
The separate GitHub requirement for one approving review remains unmet.

Local static validation passed: all four production pins match the floors in
pyproject.toml and requirements.txt; inspected LangGraph and requests bounds
accept the selected SDK/urllib3 versions. Application code, READMEs, Dockerfile,
CI workflow, and vulnerability exemptions are unchanged. Runtime CI is pending.
