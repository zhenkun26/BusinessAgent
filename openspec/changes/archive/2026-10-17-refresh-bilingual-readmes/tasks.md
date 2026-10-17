# Tasks

## 1. Preparation

- [x] 1.1 Inspect current Git state, source baseline, project instructions, and documentation conventions.
- [x] 1.2 Isolate the documentation increment from the existing PR branch and permission changes.
- [x] 1.3 Record proposal, design, scope, and verification limitations before editing the READMEs.

## 2. Implementation

- [x] 2.1 Write the Chinese README from the approved draft.
- [x] 2.2 Write a complete English translation with reciprocal language navigation.
- [x] 2.3 Update the repository index and existing development status record.

## 3. Verification and delivery preparation

- [x] 3.1 Check relative links, heading anchors, command syntax, and translation parity.
- [x] 3.2 Review final content and verify that the diff contains only this documentation increment.
- [x] 3.3 Copy both README files to the requested local folder and verify unrelated files are preserved.
- [x] 3.4 Archive this completed documentation change and prepare the scoped commit for the authorized push.

## Verification record

- PASS: each README has 21 valid repository links and 3 valid heading anchors.
- PASS: both documents have 22 headings and 11 matching fenced blocks, including
  8 Bash blocks per document checked with `bash -n` without executing commands.
- PASS: executable/configuration blocks, diagrams, environment keys, documentation
  destinations, section counts, and reciprocal language links are consistent.
- PASS: Python module paths in command examples resolve in the source tree.
- PASS: manual source/content review preserves Mock, sample-data, integration,
  formal UAT, and production-approval boundaries; no measured results are invented.
- PASS: the implementation diff is limited to the approved documentation scope.
- NOT_RUN: dependency installation, service startup, backend tests, and browser
  rendering. These static checks do not establish runtime setup success.
- UNAVAILABLE: OpenSpec CLI strict validation. Manual artifact checks do not replace it.
- PASS: both READMEs were copied to the requested local folder; SHA-256 and
  file-mode comparison preserved all 596 unrelated tracked files.
- Delivery: prepared on `codex/bilingual-readme` from main `2d4bfc17`; push and PR
  outcomes are reported in the delivery response. Merge is not authorized.

## README content fingerprints

- `README.md`: SHA-256 `2bd64747e0ab904c36d0850be7647810c36d647c1b681b4bcede656349a5b4a8`
- `README-en.md`: SHA-256 `c8f78b9e436e4214f03dde234517d33eb525b6d7e9b3042f605d6a03136fcd0c`
