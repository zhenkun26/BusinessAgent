# License and data provenance inventory

## F2-09 plan — authorized 2026-10-20

Baseline: local build-input increment `c518a2a`; portfolio/open-source presentation,
with no customer deployment planned. This plan is recorded before inventory implementation.

1. Enumerate the 98 pinned production Python distributions and their direct/transitive
   roles using the F2-04 build manifest. Record exact-release publisher license metadata,
   source URLs and evidence hashes. Metadata is a declaration, not a wheel-content audit.
2. Bind the three vendored browser packages to existing source/version/license files.
   Enumerate tracked fonts, screenshots, illustrations, research documents, sample
   documents, fixtures, seed SQL and embedded demonstration data. Record unknown source
   or rights explicitly; a synthetic label or Git author is not author confirmation.
3. Inventory other declared development/evaluation/ML/IdP dependencies, container/service
   images and model/service boundaries. Unresolved dependency closures, native bundled
   components and uninspected OS packages remain release-review gaps.
4. Add a source-distribution notice index that points to preserved upstream notices.
   Do not relicense third-party works, invent copyright holders, choose a dual-license
   branch without review, or claim an installed-image notice inventory.
5. Add a stdlib read-only verifier and offline negative tests for inventory coverage,
   version/hash drift, absent evidence and attempts to misrepresent pending rights as
   accepted. Synchronize delivery trackers and the active OpenSpec change.
6. Review the diff, run focused and relevant regression checks, then make one local
   Conventional Commit. No push, merge, publication, deployment, main-spec sync or archive.

### Acceptance for this increment

- Every production pin and vendored browser package has a versioned source/license record.
- Explicit coverage rules enumerate tracked data/media and declaration inputs; a newly
  added covered file or changed input cannot silently retain a passing inventory check.
- License expressions and available local texts are distinguished from verified rights.
  Unknown sources have a specific evidence request and remain pending.
- The verifier reads only its supplied repository; it performs no network, subprocess,
  installation, deletion, credential reading or application import.
- Offline integrity PASS does not mean license compatibility or redistribution approval.
  F2-09 remains OPEN until pending rights and actual distribution evidence are reviewed.
  Real runtime/full RAG remain BLOCKED and C10 stays OPEN.

### Initial observations

The root license is MIT, copyright 2026 zhenkun26. Vue, Marked and DOMPurify have
versioned local license files. The presentation also tracks 217 WOFF2 files from five
CSS-declared font families and 18 screenshots; no associated font license file was
found. Font names/opaque filenames do not establish exact upstream versions or rights.
Production metadata includes LGPL (psycopg) and MPL (certifi), so a blanket “all MIT”
or “all dependencies cleared” conclusion would be incorrect.

## Inventory contract

The [inventory](../../enterprise-agent/deploy/license-inventory.json) is the versioned
record. [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md) is the human-readable notice
index. Neither is a final-image SBOM, legal opinion or permission to redistribute.
Root MIT is a project declaration; it cannot establish third-party authorship.

| Scope | Recorded evidence | Remaining acceptance |
| --- | --- | --- |
| Production Python | 98 exact releases: 36 direct names in pyproject, 62 transitive/build entries; release URLs, metadata SHA-256, original license expression/legacy text/classifiers/project URLs | Actual selected Linux wheels, bundled native libraries, copyright/NOTICE files, compatibility and distribution obligations |
| Browser distribution | Vue 3.5.44, Marked 18.1.1, DOMPurify 3.4.17; 7 existing asset/license files, npm source/integrity, SHA-256 | Embedded component texts and actual delivered artifacts; DOMPurify regenerator-runtime attribution needs complete text review |
| Other declarations | 32 files covering pyproject base/dev/eval/build requirements, production/ML/IdP requirements, Compose/K8s/Dockerfiles, CI/pre-commit and model profile | Resolve exact distributions/transitive closures for each profile before making profile-specific claims |
| Source/data/media | 429 scoped files, each with path/hash/category and pending provenance status | Author/source confirmations by group below, not an automatic blanket grant |
| Final containers | Pinned production Python base and Debian snapshot references remain in F2-04; other configured service image references are enumerated | Actual OS/package copyright inventory and per-image notices; floating tags/aliases are declarations, not resolved versions |

The PyPI fields were extracted from the 98 cached official exact-release responses
already retained during F2-04. Their raw SHA-256 values and versions were checked against
`build-inputs.json` before extraction. This turn did not download wheels, contact providers,
or obtain new publisher/author assurances. Preserve `null`, non-SPDX legacy strings and
classifier-only records rather than guessing: Loguru and PyMilvus have classifier evidence
but no populated expression/legacy field in those responses. Git review is the trust
anchor for the recorded declarations; the offline verifier does not reauthenticate PyPI.

License review priority includes psycopg/psycopg-pool (`LGPL-3.0-only` in publisher
metadata), certifi (`MPL-2.0` legacy metadata), orjson/tqdm (MPL-containing expressions),
dual/multiple-license expressions, and native bundles such as NumPy, cryptography, grpcio,
lxml and compression libraries. These are review targets, not findings of noncompliance.
Do not simplify `AND`/`OR`, infer a license from an ecosystem, or select one license branch
automatically. Preserve exact upstream license files when packaging; inspect the actual
resulting image before asserting that all required notices are shipped.

## Source coverage and author confirmation queue

| Group / file count | Present source evidence | Evidence still requested / responsible party |
| --- | --- | --- |
| Presentation / 240 | Repository HTML/CSS, launch/notes, 217 WOFF2 files and 18 PNG/WebP screenshots | Author: original download/source URLs, exact font releases, accompanying texts, modification history; screenshot capture origin and confirmation of synthetic identities/content |
| Research / 4; other media / 3 | Three research Markdown files plus an executive-summary PDF; three documentation illustrations | Author: original creation/generation process, external sources, retained permissions/attribution, whether any content was copied |
| Evaluation / 68 | Includes 9 sample policy/product documents, 122 primary and 6 supplemental evaluation cases, UAT fixture and generator, scripts and historical text reports | Author: original or adapted source per corpus, right to publish, confirmation no real customer/personal data; labels and old reports alone do not establish this |
| Seed/schema / 14 | Demo/init/migration SQL retained in repository | Author: origin of inline business examples and identities; distinguish schema authorship from example-data rights |
| Reference fixtures / 11; tool fixtures / 11 | Reference HTTP/IdP files and Python tool examples | Author: authorship or adaptation sources and synthetic-data confirmation |
| Test fixtures / 65; application UI / 1 | Offline tests and UI source may embed sample text, payloads and illustrative identities | Author: group-level creation statement with any exceptions listed by path |
| Generated tooling / 12 | Codex/Kimi OpenSpec SKILL.md files declare MIT in front matter | Maintainer: precise generator package/version, full applicable license/copyright text and redistribution scope; front matter alone is metadata |

The five CSS-declared font families are Fraunces, JetBrains Mono, Manrope, Noto Sans SC
and Noto Serif SC. Their opaque local filenames are recorded individually; family names
do not prove which upstream release/license produced the binary. No font license was
invented or added from a different release. Do not publish the presentation as rights-cleared
until this is resolved. The current UAT generator explicitly describes deterministic
simulation and its fixture labels records synthetic; that supports intended use, not
independent verification of origin. The C17 corpus manifest fixes bytes and case counts,
not copyright ownership or real RAG quality.

An author confirmation can cover a coherent group but must identify exceptions and
source paths/hashes. Record who confirmed, when, exact source/version, original versus
adapted/generated status, permission/license evidence, retained notices, and any
privacy review. If evidence remains unavailable, keep the item pending or propose a
separately authorized replacement; do not silently delete, relabel or invent a source.

## External models, non-production profiles and distribution boundaries

The remote profile configures Bailian Beijing `text-embedding-v4`/`qwen3-rerank` and
DeepSeek `deepseek-flash`/`deepseek-v4-pro`; these are service identifiers, not included
model weights. Service terms, data processing and output-use rights require separate
provider/account evidence before real use (F2-05); this turn makes no API calls.
Optional BGE/Ollama/local model experiments do not inherit remote-profile acceptance:
record exact downloaded model revisions, weight/tokenizer licenses and training/data
claims available from the publisher if that distribution is later proposed.

IdP pins overlap production but are a separate distribution; development/evaluation
ranges and ML direct pins do not prove their installed transitive closure. Keep CI tools,
build tools, service images and distributed runtime assets distinct. MinIO, Redis Stack,
Grafana and other configured services require exact-image/version review; their
repository names cannot determine licensing. The production Dockerfile retains bundled
browser files through `COPY app`; Python/OS license retention still needs actual-image
inspection. No image was built and no packaging recipe was changed in this increment.

## Offline check and controlled update

From the repository root:

```bash
python3 -I -B enterprise-agent/scripts/verify_license_inventory.py
```

Exit 0 means **inventory integrity PASS**, while `distribution_acceptance` remains
**BLOCKED**. Exit 1 means missing/drifting/invalid inventory evidence. It performs no
network, subprocess, installation, application import, writes or deletion; only paths
inside the supplied root are read. Symlinks in covered trees are rejected. Results/cache
directories, `.env*`, `.log`, `.pyc` and `.DS_Store` files are excluded. No runtime log,
credential or private uploaded-data directory is inventoried.

Coverage is implemented explicitly in the verifier: interview, research, eval, tests,
reference service/IdP and generated-skill trees; documentation media; application UI,
embedded JSON/media/tool examples; deployment SQL; declaration inputs and all vendored
browser distribution files. New files under these scopes must be recorded even if not yet
tracked. This is **not** an exhaustive copyright scan of every code/comment/Markdown line
elsewhere in the repository. General project authorship/adaptations remain part of the
author confirmation. Files outside these scopes require review when the distribution
scope changes.

For an update:

1. Review the actual diff and choose the affected scope; do not auto-accept changed hashes.
2. For production dependency changes, refresh F2-04 first. Obtain exact-release metadata,
   retain the response, verify its version/name/raw hash against that manifest, and record
   unaltered license fields/classifiers. Never treat metadata refresh as wheel inspection.
3. For data/assets, retain source/version/license and author confirmation where available;
   keep pending records otherwise. Review browser headers and full license texts together.
4. Update inventory hashes and exact declaration strings. The current schema intentionally
   accepts only pending source/metadata states: admitting a verified state requires a
   separately reviewed evidence schema and tests, not changing `PENDING` to `PASS`.
5. Run focused negative tests and the read-only verifier, retain outputs, review notices
   and update the delivery ledger. Actual distribution review and publication remain
   separate gates.

## Offline delivery evidence — 2026-10-20

- **PASS:** 36 new deterministic cases; complete local pytest **1134 tests + 249 subtests**,
  zero skips/xfails/guard denials. This run used macOS arm64/Python 3.13.15 with the already
  declared F2-04 dependency view, not a new installation or a Linux image. 45 existing
  warnings remain; no tests were skipped to obtain a passing result.
- **PASS:** read-only inventory (98 Python packages / 3 browser packages / 429 scoped
  source files / 32 declaration files), F2-04 build-input integrity and existing browser
  asset verification (7 files). No provenance was silently marked approved.
- **PASS:** single-agent diff review of license evidence levels, pending-rights claims,
  source coverage, read-only verifier, notice retention and negative tests. Source syntax,
  local links, manual OpenSpec structure and preserved original files/modes are checked
  before commit; manual checks do not substitute for the missing OpenSpec CLI.
- **BLOCKED:** author/upstream rights confirmation, target wheel/native/OS distribution
  inspection, strict OpenSpec CLI, real runtime/full RAG and all previous live gates.
  F2-09 remains OPEN for those rights gaps; C10 stays OPEN.

Retained local full-suite evidence (ignored, not a portable release attestation):
`enterprise-agent/eval/results/ci-pytest-ebf7ed75f7c4461cb85de22bfb4dc6e5/receipt.json`.
The same directory retains `f209-validation.json`, test/source hashes and final commit
binding. Public source records the reproducible command, scope and result; local receipts
contain richer host-specific evidence. No remote CI, push, merge, release or archive.

## F2-11 scoped source update — 2026-10-20

The preceding counts and test results describe the F2-09 increment at `fa1fa05`.
F2-11 adds only `interview/portfolio-walkthrough.md` to the presentation scope, bringing
current inventory coverage to **430 source files** (241 presentation files). Its hash is
recorded with `PENDING_SOURCE_REVIEW`; no existing source record, license declaration or
rights status is cleared. The older interview/speech/deck files are unchanged. This is
source coverage maintenance, not a new license decision or publication authorization.

## F2-08 scoped source update — 2026-10-20

Add `enterprise-agent/tests/test_citation_time.py` and refresh only the hashes of
`test_checkpoint_followups.py`, `test_retrieval_authorization.py` and
`test_browser_delivery.cjs` under the existing test-fixtures category. Current coverage
is **431 source files**; all remain `PENDING_SOURCE_REVIEW`. Existing publisher metadata,
notices, declarations and older interview/deck bytes are unchanged. This update records
source integrity only; F2-09 author/upstream and actual-distribution review remain pending.

## F2-05 scoped source update — 2026-10-20

Add only `enterprise-agent/tests/test_data_privacy.py` as a test-fixtures record, bringing
current coverage to **432 source files**. The new synthetic test remains
`PENDING_SOURCE_REVIEW`; all preceding records, dependency declarations and rights statuses
are unchanged. This is integrity maintenance, not source-rights clearance. No old interview,
speech, deck or presentation asset is modified or uploaded.


## F2-06 scoped source update — 2026-10-20

Add the independent `eval/rag_safety.py`, `eval/rag_safety_controls.json`,
`eval/run_f206_rag_safety.py` and `tests/test_rag_safety.py` records under evaluation and
test-fixtures categories. Current coverage is **436 source files**, all with existing
`PENDING_SOURCE_REVIEW` semantics. New control content is synthetic; this does not clear
repository authorship or any prior source/license decision. Original C17 sample bytes,
older interview/speech/deck files and all preceding rights/dependency records are unchanged.


## F2-07 scoped source update — 2026-10-20

Add `tests/test_keyboard_accessibility.py` under test-fixtures; refresh only the hashes of
`app/static/index.html`, `tests/test_browser_delivery.cjs` and
`tests/test_browser_credential_safety.cjs` (all paths below `enterprise-agent/`). Current
coverage is **437 source files**, all retaining `PENDING_SOURCE_REVIEW`. This update
records integrity, not source ownership or redistribution permission. Previous dependency,
vendor/notice, C17/safety corpus and interview/speech/deck records and rights remain unchanged.


## F2-10 scoped source/declaration update — 2026-10-20

Add only `enterprise-agent/tests/test_offline_verification.py` under test-fixtures (438
source records total) and refresh `.github/workflows/ci.yml` declaration identity/items
for the aligned local/CI entry and retained coverage path. Prior source records, license
metadata and rights statuses are preserved. New scripts/source manifest are tracked by
the current-candidate integrity inventory; that coverage grants no source rights. All
F2-09 author/upstream/distribution decisions remain pending.

## F2-05 telemetry admission scoped update — 2026-10-21

Add only `enterprise-agent/tests/test_telemetry_admission.py` (synthetic configuration/
factory fixtures), bringing the controlled source inventory to **439 records**. Refresh
the reviewed W9 tracing usage comment and five existing startup/queue fixture hashes;
existing business/security assertions are preserved. Also refresh the F2-10 test hash
for its diagnostic environment cleanup regression. The new application policy is bound
by the current offline source inventory. No package, browser asset, license declaration
or rights status changes; author/upstream and final-distribution review remain pending.

## F2-06 read-only trust boundary scoped update — 2026-10-21

Add only `enterprise-agent/tests/test_rag_trust_boundary.py` (synthetic policy/model/
graph fixtures), bringing controlled coverage to **440 records**. Refresh the reviewed
`eval/rag_safety.py` provenance-input list and five test hashes: aggregator, analysis data,
data privacy, original RAG safety and token usage. Preserve the original control corpus,
C17 inputs/evaluator/denominators and all rights statuses. Policy/production source hashes
are bound by the current offline inventory (334 inputs); this grants no publication rights.

## F2-06 Planner/tool boundary scoped update — 2026-10-22

Add only `enterprise-agent/tests/test_planning_trust_boundary.py`, bringing controlled
source coverage to **441 records**. Refresh the existing context fixture hash for literal
request-owned action text and the shared real rejection class; keep its assertions.
The new production policy and five touched production modules are bound by the current
336-input offline inventory. No package/declaration/browser asset or rights status changes.
This synthetic/offline increment grants no publication rights; author/upstream/final
wheel/image notice acceptance remains pending and privacy/runtime/full RAG remain BLOCKED.

## F2-06 non-knowledge result boundary update — 2026-10-22

Add only `enterprise-agent/tests/test_nonknowledge_result_boundary.py`: **442 pending
source records**. Refresh aggregator/analysis test hashes for guards on the actual model
factory after removal of the old summary helper; existing no-model assertions remain.
The new composition module and aggregator are bound by the 338-input offline inventory.
No package, declaration, browser asset or rights status change; author/upstream and final
wheel/image notice acceptance remain pending. Parser samples/receipts are ignored local
synthetic evidence, not uploaded or redistributed project material.

## F2-06 chitchat fallback boundary update — 2026-10-22

Add only `enterprise-agent/tests/test_chitchat_trust_boundary.py`: **443 pending-source
records**. No existing fixture hash or rights status changes. Chitchat policy/aggregator/
graph are bound by the 340-input offline inventory. No package/declaration/browser asset
or license claim changes; author/upstream and final distribution notices remain pending.
Local synthetic parser/test receipts are retained and ignored, with no upload.

## F2-06 optional LLM rerank boundary update — 2026-10-22

Add `enterprise-agent/tests/test_llm_rerank_boundary.py`: **444 pending-source records**.
Refresh only the changed `test_retrieval_authorization.py` fixture hash; its source/ACL
assertions are retained. Existing source status and all package/declaration/browser/notice
records stay unchanged. The 342-input offline inventory binds the new boundary and actual
reranker/retriever/graph/tests. No dependency or rights claim; author/upstream and final
wheel/image notice review remain pending. All retained synthetic receipts stay local.

## F2-06 optional Cohere/BGE result boundary update — 2026-10-22

Add `enterprise-agent/tests/test_optional_rerank_results.py`: **445 pending-source records**.
Refresh only the adapted `test_retrieval_authorization.py` ndarray fixture hash; existing
source/ACL assertions and all rights statuses remain. The 344-input offline inventory
binds the helper/actual reranker/tests. No package, declaration, browser asset or notice
changes; no SDK/ML installation or model download. Author/upstream and actual wheel/image/
model notice reviews remain pending. Synthetic receipts are retained locally, not uploaded.


## F2-06 factory selection/status update — 2026-10-22

Add `enterprise-agent/tests/test_reranker_selection.py`: **446 pending-source records**.
Refresh only two existing isolated fixtures (`test_knowledge_publication.py` and
`test_remote_models.py`) to supply the new internal selection metadata type; all prior
ACL/publication/remote-failure assertions remain unchanged. The 345-input current offline
inventory binds those reviewed changes plus factory/retriever/config comments/provenance.
Package/declaration/browser/notice records and all rights statuses remain unchanged.
No dependency, provider call, download or upload; author/upstream/final-image reviews pending.


## F2-06 score-admission update — 2026-10-22

Add `enterprise-agent/tests/test_score_admission.py`: **447 pending-source records**.
No existing test/fixture source hash or rights status changes. The 347-input current
manifest binds the five reviewed production files, new stdlib helper/test and provenance.
Package, dependency declarations, browser assets and notices remain unchanged; no source
is silently cleared by its synthetic label. Author/upstream and actual distribution/model
notice reviews remain pending. No dependency install, real provider or upload.


## Backend samples and C17 provenance preparation — authorized 2026-10-22

### Plan recorded before worksheet preparation

Baseline: local `6f5bbd9`. This documentation-only increment covers exactly the nine
`eval/sample_docs/` files named by `rag_quality_manifest.json`, plus `eval_set.json`
and `permission_eval_set.json`. The manifest and existing license inventory are read-only
binding references, not extra items to clear. No source/fixture/code, rights status,
license admission rule, corpus, hash manifest, dependency or C17 denominator is modified.
Unknown provenance remains `PENDING_SOURCE_REVIEW` for every scoped item and all 447
registered source records. Runtime/full RAG/privacy remain BLOCKED and C10 OPEN.

1. Freeze the eleven paths, full SHA-256 values and their C17 document/suite identities
   against the current manifest and source inventory; keep primary/supplemental counts
   separate and retain all cases. Record content structure only, without copying questions,
   answers, policy text, identities or other potentially private material into this worksheet.
2. Inspect only these files and their available local path history for objective repository
   observations. Dates, fixture labels, root MIT and Git attribution are not proof of
   authorship, permission, upstream origin or synthetic-data status. Do not infer missing
   facts, search externally, contact authors/providers or upload project content.
3. Prepare stable item IDs, per-file review focus, available evidence and open questions.
   Provide a reusable author response form for original/adapted/generated contributions,
   exact upstream material/notices, collaborator rights and real-data review. Leave answers,
   confirmations, evidence acceptance and rights judgments pending; task authorization is
   not a source or redistribution declaration.
4. Reconcile the existing F2-09 ledger, roadmap and active OpenSpec artifacts. Keep older
   interview/speech/deck/media, fonts, seed/reference/tool fixtures and final distribution
   notices outside this batch. Future scope or rights-rule changes need separate authorization.
5. Review exact eleven-file membership, source/manifest/inventory/rule immutability, links,
   YAML/manual OpenSpec structure and documentation-only diff. No full pytest, model/runtime,
   CI or image execution is necessary for this prose-only increment. Existing test receipts
   remain bound to their tested revision; do not relabel them as fresh evidence for this commit.
6. Make one reviewed local documentation commit and stop for confirmation. No push/upload,
   merge, release, main-spec sync, archive, environment activation or automatic next item.

### Exit criteria for preparation

- Exactly eleven worksheet items with complete path/hash bindings and explicit pending state.
- Nine document identities plus two separate suite identities/counts match frozen C17 inputs.
- Repository observations, author answers and verified rights are visibly separate; no
  author statement, synthetic-data clearance or upstream permission is invented.
- Every item has actionable questions and a path/hash-bound response route; group responses
  list exact item IDs and exceptions. This does not change the verifier's admission policy.
- Scoped content, inventory/rules and C17 bytes/counts stay unchanged; relevant document
  checks pass while unavailable strict CLI, runtime/full RAG/privacy remain BLOCKED.
- Local documentation commit only; F2-09 and C10 stay OPEN, then wait.

<a id="backend-c17-confirmation-worksheet"></a>
### Eleven-item confirmation worksheet

Prepared against `6f5bbd92a3fa522a066eaefa433cffdf461c9402`. Worksheet identifiers D01–D09
and E01–E02 are local review labels, not replacements for C17 document/query IDs. All
paths below are existing repository inputs. At preparation (`7fad067`), each reply was
NOT PROVIDED. Current response status: **all eleven replies received; creation process
and reference sources unknown**. Source/privacy confirmation remains **PENDING** and
rights remain **PENDING_SOURCE_REVIEW**. See the [current response record](#backend-c17-unknown-source-responses);
the file identities and hashes below are unchanged.

#### Frozen item register

| Item | Existing file | C17 identity / scope | Full SHA-256 |
| --- | --- | --- | --- |
| D01 | [sample_docs/IT运维与安全制度.md](../../enterprise-agent/eval/sample_docs/IT运维与安全制度.md) | eval-c17-01 / shared_company | `5d4286882a48a5dec9a16bc6f82780ecc74c7cecab4155f994f28707600411b8` |
| D02 | [sample_docs/dept_finance/财务部预算审批细则.md](../../enterprise-agent/eval/sample_docs/dept_finance/财务部预算审批细则.md) | eval-c17-02 / dept_finance | `37f93abbd2f008c2cc606ca4976cfc61870410270c8117bd246b092c8c8cc5b7` |
| D03 | [sample_docs/dept_sales/销售部内部激励方案.md](../../enterprise-agent/eval/sample_docs/dept_sales/销售部内部激励方案.md) | eval-c17-03 / dept_sales | `a061e61c936852c8f3a8a06bf29a7e985dc39ae6036433e07d160c52f74bacb8` |
| D04 | [sample_docs/产品手册.md](../../enterprise-agent/eval/sample_docs/产品手册.md) | eval-c17-04 / shared_company | `7ccef504af15f608ffdcaa38a9dff234ff168fb8ffa5a2dffe40e1eec2fdb328` |
| D05 | [sample_docs/人事管理制度.md](../../enterprise-agent/eval/sample_docs/人事管理制度.md) | eval-c17-05 / shared_company | `ca94bda5a76df6c4f121a56ff0d04ba02547116c980098c3ff624c65f859d7c0` |
| D06 | [sample_docs/售后服务政策.md](../../enterprise-agent/eval/sample_docs/售后服务政策.md) | eval-c17-06 / shared_company | `f63f0344db76c73cd310e69f053717e6191a5dc4b284fd01cbf0acbab82ebb3d` |
| D07 | [sample_docs/常见问题FAQ.md](../../enterprise-agent/eval/sample_docs/常见问题FAQ.md) | eval-c17-07 / shared_company | `372a664ad1bb8a1461012ba4ceba6ab5a310a4c6b1b250cc46ed39e7b4d51890` |
| D08 | [sample_docs/财务报销制度.md](../../enterprise-agent/eval/sample_docs/财务报销制度.md) | eval-c17-08 / shared_company | `b781104c86183f631f7b761fd8d1b8b3fe4d44205e69bdb04927a8a1500ccd56` |
| D09 | [sample_docs/销售政策.md](../../enterprise-agent/eval/sample_docs/销售政策.md) | eval-c17-09 / shared_company | `814e3d8832563f2d5ba4f640d47240d55cf6c2e47a510fcf256774f9cdb1090b` |
| E01 | [eval_set.json](../../enterprise-agent/eval/eval_set.json) | primary / 122 cases | `ae4304f0ed16263ea9d00cd1091435737e7a44a5c13b66dbee58bd1fa1437bcc` |
| E02 | [permission_eval_set.json](../../enterprise-agent/eval/permission_eval_set.json) | supplemental / 6 cases | `099a01828a6f8f78beac62bcf409f95fafff41f7a7b26f9bc570b9653bd1b929` |

The nine document IDs/namespaces come from the unchanged C17 manifest. Namespace/role
visibility defines a test access boundary; it is not evidence of ownership or permission
to publish. The complete file hashes bind all text and rows, not just the observations
summarized here. No question/answer text, policy clause, identity or contact detail is copied.

#### Repository observations, not provenance conclusions

| Items | Available local fact | What remains unestablished |
| --- | --- | --- |
| D01–D09 | UTF-8 Markdown at the manifest paths, matching C17 and pending source-inventory hashes. A literal http(s) URL scan found no matches in these nine files. | Original authors/contributors, original versus adapted/generated portions, external policy/template sources, publication authority and whether examples derive from real data. No URL match does not prove no upstream source. |
| E01 | JSON version 2.0; declared total and actual unique query-ID count are both 122. Existing behavior classification: 115 normal answers (including omitted behavior defaults), 5 refusal and 2 clarification cases. | Who composed queries, keywords and ground-truth references; how they were derived; any adapted cases or real user questions. IDs are not assumed consecutive: exceptions must name actual IDs, not an inferred Q001–Q122 range. |
| E02 | JSON version c17-acl-v1; 6 unique query IDs ACL001–ACL006, 2 answer and 4 refusal cases. Rows include role/department, forbidden-source/keyword and provenance fields. | Authorship, derivation from E01/D01–D09 or other material, ownership/permission and whether identities or denied facts derive from real records. A provenance field is a declaration, not independent verification. |

C17 remains two separate suites: **122 primary / 6 supplemental**, with **115/7** and
**2/4** normal/behavioral splits. The 128 rows are neither merged into a new metric nor
reduced to a selected sample. This worksheet does not add evaluation cases, change
expected answers, tune metrics or perform semantic/model acceptance.

Available local path history (commit and committer timestamp, including original offset):

| Items | Oldest observed local path-history entry | Latest observed local path-history entry |
| --- | --- | --- |
| D01, D05 | `862d2952e8774fb04a58e06824151a5fa6f9af6b` / 2026-08-06T12:04:09+08:00 | `862d2952e8774fb04a58e06824151a5fa6f9af6b` / 2026-08-06T12:04:09+08:00 |
| D02, D03, D04, D06, D07, D08, D09 | `b4cca93b762724c4070276b0bddb098811632ecd` / 2026-08-04T08:19:57+08:00 | `b4cca93b762724c4070276b0bddb098811632ecd` / 2026-08-04T08:19:57+08:00 |
| E01 | `b4cca93b762724c4070276b0bddb098811632ecd` / 2026-08-04T08:19:57+08:00 | `862d2952e8774fb04a58e06824151a5fa6f9af6b` / 2026-08-06T12:04:09+08:00 |
| E02 | `cd49d788ed4ecea00e9db22d414917f91f32a886` / 2026-10-17T23:29:39-04:00 | `cd49d788ed4ecea00e9db22d414917f91f32a886` / 2026-10-17T23:29:39-04:00 |

These are observations from `git log --follow` in the available, non-shallow local
repository. They do not establish original creation dates, authorship, upstream origin,
rights ownership or the truth of timestamps. No remote history was fetched, no author
identity/email is reproduced, and no permission is inferred from commit attribution.

#### Questions for each item

Answer common questions C1–C6 below, then address the row-specific focus. Review focus
comes from the filename/C17 purpose; it is not an allegation that content was copied or
that real data is present. Do not paste private policy text, prompts or identities as evidence.

| Item | Additional author/source confirmation needed |
| --- | --- |
| D01 | Were the IT/security procedures written for this fixture, adapted from a template or generated? Identify the origin of any borrowed procedure/security wording and whether any operational example is real. |
| D02 | Confirm the origin of budget/approval rules, organizational roles and any numeric thresholds; identify copied/adapted policy portions and the authority to publish them. |
| D03 | Confirm the origin of incentive/compensation examples and policy wording; state whether they describe fictional examples or derive from an actual employer/customer document. |
| D04 | Identify the origin of product names, feature descriptions and specifications, including any vendor/marketing text or generated sections. Which claims/examples are authored fixtures? |
| D05 | Identify the origin of HR-policy wording and any organization/person-related examples; distinguish fixture creation from adaptation of actual internal material. |
| D06 | Identify the origin of after-sales terms and examples, including any reused commercial-policy/template language and its applicable permission/notices. |
| D07 | Were the FAQ questions/answers independently authored, derived from D04/D06 or other inputs, adapted or generated? Identify actual dependencies and exceptions by section. |
| D08 | Confirm the source of reimbursement rules/amount examples and any external-policy/template contributions; state whether any example reflects real records. |
| D09 | Identify the source of sales-policy wording, tiers/threshold examples and any organization/customer-related data; distinguish fixture-only content from adapted material. |
| E01 | Who created the 122 queries, keyword labels and ground-truth document/section references? Were they written from the nine documents, generated, imported or adapted? List every different-source exception by query_id and contributor/source. |
| E02 | Who created the six role/permission controls and forbidden facts? Identify derivation from D01–D09/E01/other inputs by query_id, including any copied text, generated input or real identity/data contribution. |

Common questions (creation process/reference sources now answered as unknown; remaining
details and supporting evidence are unestablished, as recorded in the current response record):

| ID | Required author statement / evidence request |
| --- | --- |
| C1 — Creation | Identify the creator/contributor role and contribution scope; original, adapted, generated, mixed or unknown. State known creation context/date without guessing missing facts. |
| C2 — Upstream | For any upstream contribution, identify exact source/version/section, original versus modified portions, applicable license or permission and retained attribution/NOTICE requirements. If unknown, write unknown. |
| C3 — Generation | If generated, identify known tool/model/version/date and summarize input origins and human edits. Supply only non-sensitive evidence references; do not paste private prompts or credentials. Generation alone is not rights clearance. |
| C4 — Data origin | Confirm whether organization/person/customer identifiers, examples and policy facts are fixture-only or derived from real material. Identify exceptions by path/section/query_id and review needs without reproducing private data. A synthetic label is not an automatic privacy approval. |
| C5 — Authority | Identify who can authorize publication of the relevant contribution, any employer/client/collaborator restrictions, and evidence of applicable permission. Root MIT or task authorization does not grant third-party rights. |
| C6 — Evidence and exceptions | Provide dated, path/hash-bound supporting references and exact exceptions. Distinguish a proposed use from an existing permission; leave unsupported statements pending. |

#### Author response form — retained preparation template

This blank template is retained from `7fad067`; NOT PROVIDED below denotes unfilled
template fields, not the current response status. All eleven received replies are recorded
separately in the current response record. Keep the template distinct from those replies.

A response can cover one coherent group only if it explicitly lists each item ID/full
hash (or the exact unchanged register at the baseline above) and all exceptions. Do not
apply a statement to all 447 records, other files, future revisions or unrelated materials.
Any content/hash change requires a separate scope and binding review.

```text
Covered item IDs and full SHA-256 / exact register baseline: NOT PROVIDED
Responder role and authority for these contributions: NOT PROVIDED
Statement date: NOT PROVIDED
C1 creation and contribution scope: NOT PROVIDED
C2 upstream source/version/permission/notices: NOT PROVIDED
C3 generation/input origins/human edits, if applicable: NOT PROVIDED
C4 real-data review and identified exceptions: NOT PROVIDED
C5 publication authority/restrictions and evidence: NOT PROVIDED
C6 evidence references and path/section/query_id exceptions: NOT PROVIDED
Unresolved or unknown facts: NOT PROVIDED
Evidence review: PENDING (no reviewer finding entered)
Rights state: PENDING_SOURCE_REVIEW (unchanged)
Privacy/runtime/full RAG acceptance: BLOCKED (unchanged)
```

Preparation and a later author statement are separate from evidence acceptance. Do not
replace NOT PROVIDED with inferred statements. Record a future statement as supplied,
review its scope/evidence and retain unknown facts; this increment authorizes no rights
transition or change to the verifier, inventory, license terms, source bytes or C17 corpus.
Do not invent an owner, signature, permission date, absence of third-party inputs or
confirmation of synthetic data. No legal clearance or public-distribution approval is made.

#### Read-only binding references

These identities anchor this worksheet; they are not additional source-clearance items.

| Reference | SHA-256 at the baseline |
| --- | --- |
| `enterprise-agent/eval/rag_quality_manifest.json` | `90834d1cbd4a969e8d7610747494ff2c91c1d9bbfaad7d8b58436a7e696b2a6e` |
| `enterprise-agent/deploy/license-inventory.json` | `1bd22077a91e8fb30467facb8bcf8ff07422dd425a19ce70aae401212d55fcdf` |
| `enterprise-agent/scripts/verify_license_inventory.py` | `3de1cc81df7d260c2709efe24477d0e1211aac9b9b773838bf011c8344a6455d` |
| `enterprise-agent/scripts/offline_sources.json` | `c50b487c47ed3ab4dbcd67f61fbb2aec99ec5cf044d60ffba3f293c9fe4dfc45` |

### Preparation verification record — 2026-10-22

Historical preparation evidence for `7fad067`; the later received-response update and its
verification are recorded below. These results are not a new candidate/runtime receipt.

- **PASS — membership and binding:** exactly D01–D09/E01–E02; every full file SHA-256
  matches current bytes, the frozen C17 manifest and the existing source inventory. Nine
  document IDs/namespaces and both suite identities match. Primary 122/supplemental 6,
  unique query IDs and behavior splits 115/7 and 2/4 are unchanged. All eleven local
  path histories and the four read-only reference hashes were checked against `6f5bbd9`.
- **PASS — scope and pending states:** all 447 source records remain
  PENDING_SOURCE_REVIEW and the entire inventory is byte-identical. Backend, CI, main
  specifications, interview materials and root license are unchanged. The diff contains
  only eleven existing documentation/configuration files, with no new or deleted files.
  No source text, question/answer, identity or private policy is reproduced in this worksheet.
- **PASS — document review:** 346 local Markdown link targets and worksheet anchors,
  YAML parsing, scoped OpenSpec requirement/scenario/task structure and whitespace checks.
  The questions/form were reviewed for item scope, unanswered fields and separation of
  observed facts from rights/privacy conclusions. Read-only local Python/Git checks did
  not import application code, contact a service or change evaluation inputs.
- **BLOCKED — strict validation and acceptance:** OpenSpec CLI is unavailable; manual
  structure review is not strict CLI validation. Author/upstream evidence and source
  rights remain pending; privacy, real runtime and full RAG remain BLOCKED, C10 OPEN.
  No full pytest, eight-check candidate execution, remote CI, image build or live run was
  performed. Older test receipts retain their own revision bindings.
- **Delivery:** reviewed local documentation commit only, then wait for confirmation.
  No push/upload, external lookup/contact, main-spec sync, merge,
  release, archive or automatic next item. F2-09 is OPEN; preparation is not confirmation
  of authorship, permission, synthetic-data status or public-distribution readiness.

## Unknown-source response recording — authorized 2026-10-22

### Plan recorded before updating responses

Baseline: local `7fad067bfc221ce1cc08dce4bb07b879735587cd`. The maintainer has now answered
D01–D09 and E01–E02 individually in the current project conversation: the specific
creation process and reference sources cannot presently be recalled and must be recorded
as unknown, retaining PENDING. This increment records those received answers only.

1. Reuse the existing eleven-item register and its full path/hash/C17 bindings. Do not
   expand to the remaining source records, older presentation assets or other datasets.
2. Record eleven received responses whose creation process and reference sources are
   unknown. Keep the original/adapted/generated classification, real-data status, rights
   authority and supporting evidence unestablished. Do not invent dates of creation,
   signatures, generation tools, upstream sources, permission or synthetic-data clearance.
3. Update the active worksheet's response status and explain that the prior preparation
   record and blank form describe the earlier state/template. Preserve their historical
   evidence and keep received answers distinct from provenance verification.
4. Reconcile current delivery/issue/roadmap/index/context and active OpenSpec artifacts.
   Do not change code, corpora, manifests, inventories, admission rules or rights states;
   no main-spec sync or archive. All 447 source records retain PENDING_SOURCE_REVIEW.
5. Check exact item membership and source/reference SHA-256 values, baseline byte
   equality, C17 primary 122/supplemental 6 and existing behavior splits, pending states,
   local links, YAML/manual scoped OpenSpec and the documentation-only diff. Do not
   rerun full pytest/current-candidate/runtime entries for this prose-only change or reuse
   old receipts as fresh acceptance. Unavailable strict OpenSpec CLI remains BLOCKED.
6. Review and make one local documentation commit, then stop for confirmation. No push,
   upload, remote CI, provider/service call, dependency, merge, release or automatic next item.

### Exit criteria for response recording

- Exactly eleven received-response entries bind to the unchanged existing register;
  creation process/reference sources are unknown for every item.
- The active worksheet no longer describes these replies as absent. Unanswered details,
  accepted evidence, rights and privacy remain separate and pending/unestablished.
- Source/corpus/inventory/rule bytes, C17 categories/metrics/denominators and all pending
  states are unchanged; scoped documentation checks pass.
- F2-09 and C10 stay OPEN; real runtime, full RAG, privacy and unavailable strict CLI
  remain BLOCKED. Deliver only the reviewed local commit and wait.

<a id="backend-c17-unknown-source-responses"></a>
### Eleven received responses — creation process and reference sources unknown

Recorded against local `7fad067bfc221ce1cc08dce4bb07b879735587cd` and the unchanged
[eleven-item register](#backend-c17-confirmation-worksheet). Each row inherits only its
listed D/E item's existing full path, SHA-256 and C17 identity. This record covers exactly
these eleven files, with no extension to other records, revisions or assets.

Evidence basis: the maintainer individually replied for D01–D09 and E01–E02 in the
current project conversation, saying the specific creation process and reference sources
cannot presently be recalled, asking to record them as unknown and retain PENDING.
The following is an English summary of those received replies. The recording date describes
this documentation work; no original creation date or signature is inferred. No supporting
source, permission or real-data evidence was supplied with these replies.

| Item | Existing file / suite | Reply receipt | Creation process | Reference sources |
| --- | --- | --- | --- | --- |
| D01 | IT运维与安全制度.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D02 | dept_finance/财务部预算审批细则.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D03 | dept_sales/销售部内部激励方案.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D04 | 产品手册.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D05 | 人事管理制度.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D06 | 售后服务政策.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D07 | 常见问题FAQ.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D08 | 财务报销制度.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| D09 | 销售政策.md | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| E01 | eval_set.json / primary 122 cases | Received | Unknown; not presently recalled | Unknown; not presently recalled |
| E02 | permission_eval_set.json / supplemental 6 cases | Received | Unknown; not presently recalled | Unknown; not presently recalled |

For all eleven rows: source/privacy confirmation remains PENDING and inventory rights
remain PENDING_SOURCE_REVIEW. The reply receipt is documentation only; no inventory field,
license/admission rule or rights state is changed. The other source records receive no
inferred answer or clearance; all 447 registered records remain pending.

#### Unresolved details and evidence gaps

- **Creation/contributions:** the explicit answer is unknown creation process/reference
  sources. Specific contributors, dates and original/adapted/generated classification
  remain unestablished; no original-author declaration is substituted for that answer.
- **Upstream/generation:** exact sources, versions, borrowed sections, tool/model/input
  origins, human edits, permissions and notices remain unestablished. Unknown does not
  establish the absence of third-party contributions.
- **Data and publication:** whether material derives from real organizations, people,
  customers or internal records, and who has publication authority or restrictions,
  remain unestablished. The replies do not certify fictional/synthetic data or privacy.
- **Evidence/review:** the received replies establish what the maintainer currently
  recalls. No accepted upstream/permission evidence or rights determination is recorded.
  Further evidence must identify the exact item/hash and exceptions in a separately
  authorized review; this increment authorizes no replacement corpus or rights transition.

C17 remains primary 122/supplemental 6 with existing normal/behavioral splits 115/7 and
2/4. Corpus, evaluator, metric definitions and denominators are unchanged. F2-09 and C10
remain OPEN; privacy, real runtime and full RAG remain BLOCKED. No next item starts here.

### Response-record verification — 2026-10-22

- **PASS — reply accuracy and scope:** exactly eleven received/unknown rows bind by D/E
  ID and filename/suite to the original register. The complete register and blank template
  are unchanged; active wording now distinguishes received replies from the earlier absent
  replies/template. Review retains unestablished details and avoids inferred rights/privacy.
- **PASS — immutable inputs:** all eleven current file hashes match C17, inventory and
  baseline bytes; all four reference hashes/bytes match `7fad067`. The entire backend,
  CI, main specifications, interview assets and root license are unchanged. All 447 source
  statuses remain PENDING_SOURCE_REVIEW; no inventory or admission-rule change.
- **PASS — C17 and documents:** primary 122/supplemental 6, unique IDs and normal/behavioral
  splits 115/7 and 2/4 remain unchanged. The diff contains only eleven existing documentation/
  configuration files. 350 local link targets, 10 worksheet-anchor references, YAML parsing,
  manual scoped OpenSpec requirement/scenario/tasks and whitespace checks pass.
- **Limits:** no full pytest, current eight-check candidate receipt, remote CI, image,
  model or service execution was performed for this prose-only increment. Older receipts
  retain their tested revisions. OpenSpec CLI is unavailable, so strict validation remains
  BLOCKED; manual structure review is not a substitute.
- **Delivery:** reviewed local documentation commit only, then wait for confirmation.
  Received unknown replies grant no source/privacy/rights clearance. F2-09 and C10 remain
  OPEN; real runtime/full RAG/privacy BLOCKED. No push/upload, main-spec sync, merge,
  release, archive or automatic next item.

## F2-11 current walkthrough evidence binding — 2026-10-22

After local `ccd3065`, the existing `interview/portfolio-walkthrough.md` gains a current
candidate source/evidence section and retains its complete fa1fa05 historical body.
Its single existing source-record SHA-256 changes from
`c20f8466b3a6a92bb247f8ef30fa00e874981a494ee01176cfa9b96d56e14863` to
`d196b6a36cf13b64286710b0fd8c9f42cbad3e75dde71052509756bb2b93eb4b`.
The inventory SHA-256 becomes
`0e2e0097c5412bff8787c322e5b0f12d8fcb9bcba266cd0d68bdda97ecfa2ea9`;
only its corresponding current `offline_sources.json` source-hash field is refreshed.

All other 446 source records, categories, statuses, package/declaration data, inventory
history and admission rules are unchanged. There are still 447 pending records; this
walkthrough remains PENDING_SOURCE_REVIEW. The eleven received unknown-source replies
and C17 corpus/metrics/counts remain unchanged. Older hash tables and receipts retain
their stated baselines; they are not auto-refreshed into evidence for this update.
No original-author, synthetic-data, privacy, redistribution or actual-distribution
clearance is granted. Real runtime/full RAG/privacy remain BLOCKED, C10 OPEN.
