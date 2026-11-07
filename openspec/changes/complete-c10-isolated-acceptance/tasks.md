# Tasks
- [x] Record normative gaps and plan before implementation.
- [x] Revalidate latest candidate PG direct-store scenarios locally, retaining initial endpoint/username fixture failures.
- [x] Confirm official declared Redis Stack digest and new isolated fixture.
- [x] Make portable fail-closed Phase A harness with unique synthetic inputs and source binding.
- [x] Add isolated Linux phase job without changing existing jobs or security gates.
- [ ] Independently review and execute exact committed CI evidence.
- [ ] Complete all remaining normative scenarios; do not infer full C10 from Phase A.

## Local implementation evidence
The original retained adapted harnesses passed latest-candidate PG 17 + 24 + 5 checks and Redis saver 17 checks. Portable PG baseline passed 17; portable Redis behavior passed 17 but source binding failed when parallel work added a file; the portable fault run stopped at its 16th source-stability assertion, leaving later cases unrun. These are preserved failures, not a complete portable PASS. Six pure controls and explicit-execute/optimization/non-Linux refusal paths passed. Three owned fixture containers were stopped with volumes retained. Final clean Linux CI is required.

## Configuration isolation correction
Review found that inherited PYTHON_DOTENV_DISABLED is not a reliable boundary for the installed dotenv_values/Pydantic path. All application children and nested workers now use the new retained run cwd; Git observations still use the repository. Children receive only a minimal process allowlist plus explicit C10 fixture settings, with no inherited provider keys, model profile or telemetry. Ten no-network controls passed with actual Settings: an empty run cwd passed, while a synthetic .env in the wrong cwd was caught by an audit trap. AST controls bind every application spawn to its intended cwd. No synthetic-demo profile is enabled by C10.
