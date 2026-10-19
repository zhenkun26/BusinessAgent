# Engineering delivery status and handover

Reviewed: 2026-10-19. Change: `engineering-delivery-closeout`.
**Conclusion: offline reconciliation and remote CI repair delivered; NOT_ACCEPTED_FOR_RELEASE.**
C01–C25 remain open as whole acceptance items. No real enterprise users, formal UAT,
grey release or production approval are established. C10 lease-expiry write fencing is
an unresolved implementation defect, not merely missing environment evidence.

## Candidate and version identity

| Identity | Verified value / boundary |
| --- | --- |
| Working branch | `codex/delivery-ci-gates`; reuse existing integration roles |
| C24 pushed candidate | `d8a26b5726cb7ffce6747b677804c7c3403bd763`, same-name origin verified |
| C25 pushed increment | `fe2ae78b5102cc9cc2c4e08e4939da20fd53720e`, same-name origin verified |
| CI repair increment | `b8c4457542781029333de8c3c930437fb28ef51a` pushed; scanner follow-up `16c882b` and image-context fix `0d1a7ce2c26bedc4894c957c875648f131eb2993` pushed |
| Main at inspection | Local/main, origin/main and remote main all `065bdf7b31ce1fb6f9007a7e8851be36bfc2280f`; ancestor of C24 |
| Source/package version | `app/__init__.py` and `pyproject.toml`: `1.3.0`; closeout changes remain Unreleased |
| Historical tag | `v1.3.0` resolves locally to `731864087d081c58324e17824c79a0afffc385a1`; it does not identify this candidate |
| Database schema | Ordered migrations v1–v7 with pinned checksums; startup does not apply them |
| Image | CI-only build/import/Trivy PASS at `0d1a7ce`; digest in repair record; deployment acceptance BLOCKED |
| Document versions | Older v1.5/v3.7 headers identify document revisions/history, not application releases |
| OpenSpec | 15 main specs, 15 archived changes, three active changes; current deltas remain active/unsynchronized |
| Local preservation | 556 existing mode-only differences retained; excluded from the task commit |

Do not bump a version, move a tag or infer a release from a local documentation commit.
A source version cannot distinguish unreleased builds: use commit + image digest + schema
checksums + model/fixture identity for future runtime acceptance. A CI-only image was built
and scanned; no image was published or deployed, no PR merged,
and no specifications synchronized or archived in this increment.

## Git and CI observation

Read-only GitHub observations on 2026-10-19:

- [PR #2](https://github.com/zhenkun26/BusinessAgent/pull/2),
  `docs: close delivery records and advance offline readiness`, remains OPEN against `main`;
  inspected head `d8a26b5`, `mergeStateStatus=BLOCKED`, `reviewDecision=REVIEW_REQUIRED`.
  Its title predates the expanded closeout implementation; update scope/title/body only in
  a separately authorized remote PR update. No review approval or merge was submitted.
- [C24 CI run 39204305429](https://github.com/zhenkun26/BusinessAgent/actions/runs/39204305429)
  is **FAIL**: both Python 3.11 and 3.13 test jobs failed, production image build skipped.
  Both fail collection at `tests/test_security_hardening.py`, which imports removed
  `_redact_url` from `app.graph.checkpointer` (`ImportError`). Local source confirms that
  stale import. Subsequent local full-suite repair is recorded below; the old run remains FAIL.
- [C23 CI run 39202178839](https://github.com/zhenkun26/BusinessAgent/actions/runs/39202178839)
  also failed collection in that file. This is observed failure, not an unrun BLOCKED check.
- [C25 CI run 39205591288](https://github.com/zhenkun26/BusinessAgent/actions/runs/39205591288)
  at pushed `fe2ae78` also fails the same import in Python 3.11/3.13 (logs verified).
- The separately authorized local CI repair passes **871 tests + 225 subtests, zero skips**,
  with **73.40% local line coverage**. It replaces stale contracts and separates shared
  fixtures from test classes; all 440 original test bodies across the 13 fixture-related
  files remain identical. No CI gate, production behavior or dependency declaration changed.
  See [repair record and environment](../40-process/ci-pytest-repair.md).
- [Repair CI 39208343449](https://github.com/zhenkun26/BusinessAgent/actions/runs/39208343449)
  on `b8c4457`: Linux Python 3.11/3.13 each pass **871 tests + 225 subtests, zero skips**,
  with 75% reported coverage. Gitleaks then fails on 16 verified source-hash false positives.
  Scanner follow-up `16c882b` adds only exact historical fingerprints and a complete
  event-head scan. Run 39208901960 passes both test/security jobs but fails Docker COPY
  because the build context excludes two required scripts. Narrow context exceptions and
  one additional regression are implemented in `0d1a7ce`.
- [CI 39209313444](https://github.com/zhenkun26/BusinessAgent/actions/runs/39209313444)
  on `0d1a7ce` is **PASS**: each Python version runs **872 tests + 225 subtests, zero skips**,
  Gitleaks and pip-audit pass, production image build/non-root imports/assets pass, and
  Trivy HIGH/CRITICAL reports zero findings under its unchanged policy. No image is published.
  See the repair record for PR merge-ref/image digest identities and retained limitations.

The historical fixed offline inventory did not collect this legacy pytest file. Its 789
passing cases
and CI collection failure measure different scopes; neither cancels the other. Retain the
failure explicitly in [ISSUES C24/C25](../40-process/ISSUES.md#c24). The local repair now
covers the complete pytest suite separately, without skips or collection exclusions;
the image-context regression increases the current fixed inventory to 790 passing tests
plus its one separately BLOCKED PyYAML check; full remote pytest has zero skipped tests.

## Support and migration map

These are implemented candidate contracts and target boundaries, not measured support claims.

| Area / items | Source and current authority | Current boundary / remaining acceptance |
| --- | --- | --- |
| Deployment C01 | `docker-compose.prod.yml`, [deployment guide](../../enterprise-agent/deploy/DEPLOY.md) | Single organization, single Linux host, immutable shared API/worker image; real entry/image acceptance BLOCKED; K8s/multihost HA outside target |
| Models C02 | `.env.example`, `app/rag/model_profile.py`, [profile](../../enterprise-agent/deploy/MODEL_PROFILE.md) | Beijing embedding/rerank; Flash default, Pro complex tasks; separate collection and credentials; paid probes opt-in; no actual API/quotas/cost/latency acceptance |
| Schema C03 | `deploy/schema_manifest.json`, [bootstrap guide](../../enterprise-agent/deploy/DATABASE_BOOTSTRAP.md) | Explicit apply/status/admin; old stores only approved isolated copies; no automatic DDL, universal account or historical-token migration |
| Identity C04–C07 | [session](session-ownership.md), [authorization](runtime-authorization.md), [credentials](credential-safety.md), [retrieval](retrieval-authorization.md) | Owned sessions, current role/department authorization, no stored JWT, fail-closed rendering; actual JWT/PG/Milvus/browser/history remediation BLOCKED |
| State C08–C10 | [context](request-context.md), [coordination](cross-process-state.md), [checkpoint](checkpoint-durability.md) | Independent subtasks only; explicit Redis/PG backend, no fallback; real two-process semantics and **C10 write fencing open** |
| Execution C11–C14 | [approval](approval-execution.md), [operations](tool-operation-safety.md), [Saga](saga-recovery.md), [queue](queue-reliability.md) | Persisted claims/identities/jobs, conservative uncertainty, linked HTTP inverses; requester resume/current authorization; real locks/crashes/HTTP effects unverified |
| Knowledge C15/C17 | [publication](knowledge-publication.md), [quality](rag-quality.md) | Explicit publication visibility; legacy unversioned data needs reviewed reimport; 122 quality cases plus six role controls require actual model/store and semantic acceptance |
| Analysis C16 | `app/agents/analysis.py`, `app/tools/analysis_data.py`, [adapter](analysis-data.md) | CRM provider-aligned bounded snapshot, deterministic Python report; Mock is synthetic, HTTP real acceptance BLOCKED; no arbitrary SQL/BI support |
| Reference C18/C19 | [business HTTP](reference-integration.md), [controlled SSO](controlled-sso.md) | Independent reference CRM/ticket/mail/IdP are candidates, not actual enterprise SaaS/SMTP/IdP acceptance; R01–R20/S01–S16 BLOCKED |
| Browser C20 | [browser delivery](browser-delivery.md) | Verified current identity, local assets, transient tokens, API-only management where documented; B01–B16 BLOCKED |
| Observability C21 | [runtime observability](runtime-observability.md) | Schema v7, retained shared audit store/replay, process readiness/metrics/alerts; O01–O16 BLOCKED |
| Recovery C22 | [retained recovery](retained-recovery.md) | Current-version cold capture, fresh-volume restore, explicit compatible rollback; no hot backup/PITR/destructive cleanup; D01–D16/RTO/RPO BLOCKED |
| Capacity C23 | [capacity](capacity-evidence.md) | Proposed frozen mixed workload, separate TTFT/full response/queue timing; no measured maximum capacity or SLA; L01–L16 BLOCKED |
| Evidence C24/C25 | [fixed verification and per-item counts](final-candidate-verification.md), [ISSUES](../40-process/ISSUES.md#engineering-closeout) | E0/E1 receipts are not E2/E3/E4, full pytest, image scans or release acceptance |

Compatibility changes are Unreleased: authentication/session guards, task `202` responses,
approval resume/claim semantics, knowledge visibility, explicit migrations, external model
profile and immutable deployment require the current guides. Historical claims of unchanged
API behavior in the August changelog do not apply to these closeout changes. Do not run old
schema SQL, direct unversioned ingestion, default-user demonstrations or cleanup recipes on
current data. Preserve old BGE collections/volumes and historical credential evidence.

## Increment provenance

All listed commits are ancestors of the pushed C24 candidate. These are delivered
increments, not closed acceptance items. Each record retains its original evidence scope.

| Item | Commit | Delivery record |
| --- | --- | --- |
| C01 | `2a9c364` | [Record](../40-process/阶段性总结_C01部署产物与入口.md) |
| C02 | `42bfc7f` | [Record](../40-process/阶段性总结_C02模型依赖.md) |
| C03 | `fc8da91` | [Record](../40-process/阶段性总结_C03数据库迁移与初始化.md) |
| C04 | `dbc8236` | [Record](../40-process/阶段性总结_C04会话归属校验.md) |
| C05 | `9f5397c` | [Record](../40-process/阶段性总结_C05认证失败闭合与运行时授权.md) |
| C06 | `6955133` | [Record](../40-process/阶段性总结_C06凭证与HTML失败安全.md) |
| C07 | `ceae708` | [Record](../40-process/阶段性总结_C07检索权限与表达式编码.md) |
| C08 | `d81c281` | [Record](../40-process/阶段性总结_C08请求上下文与子任务依赖.md) |
| C09 | `079cd62` | [Record](../40-process/阶段性总结_C09跨进程运行状态.md) |
| C10 | `a57bd4e` | [Record](../40-process/阶段性总结_C10检查点持久化与故障语义.md) |
| C11 | `8bb6241` | [Record](../40-process/阶段性总结_C11审批领取与执行状态.md) |
| C12 | `21b5287` | [Record](../40-process/阶段性总结_C12工具幂等与安全重试.md) |
| C13 | `c42dcf8` | [Record](../40-process/阶段性总结_C13Saga持久化与故障恢复.md) |
| C14 | `59a5c14` | [Record](../40-process/阶段性总结_C14队列可靠性与Worker初始化.md) |
| C15 | `0c0c5f9` | [Record](../40-process/阶段性总结_C15知识发布与索引一致性.md) |
| C16 | `bb81833` | [Record](../40-process/阶段性总结_C16分析数据适配.md) |
| C17 | `cd49d78` | [Record](../40-process/阶段性总结_C17RAG质量与指标口径.md) |
| C18 | `bd04a12` | [Record](../40-process/阶段性总结_C18完整参考HTTP业务集成.md) |
| C19 | `4afe54b` | [Record](../40-process/阶段性总结_C19受控IdP与SSO完整链路.md) |
| C20 | `44bfcb0` | [Record](../40-process/阶段性总结_C20浏览器角色流程与前端交付.md) |
| C21 | `40c10d8` | [Record](../40-process/阶段性总结_C21就绪审计指标与告警.md) |
| C22 | `d70c1b4` | [Record](../40-process/阶段性总结_C22当前版本备份恢复与回退.md) |
| C23 | `6de94c6` | [Record](../40-process/阶段性总结_C23规定负载下的性能与容量.md) |
| C24 | `d8a26b5` | [Record](../40-process/阶段性总结_C24最终候选离线验证.md) |

S0 `05d8d0c`, safety prework `a329603` and the C18 contract prework `317aa7f` remain
separate earlier increments; they do not replace final runtime acceptance.

## Documentation and specification authority

1. Current executable source/config/schema establishes implemented behavior.
2. [Engineering baseline](engineering-delivery-baseline.md) establishes the target support scope;
   [ISSUES](../40-process/ISSUES.md#engineering-closeout) establishes acceptance, and
   [ROADMAP](../40-process/ROADMAP.md#engineering-closeout-stages) establishes sequence.
3. Current engineering contracts linked above govern model, migration, UI and operations.
   Chinese/English root READMEs have equivalent current setup and boundary statements.
4. July/August manuals, W-stage measurements, archived OpenSpec changes and interview
   assets preserve historical/design/demo context. Their old model names, fallback paths,
   timings, sample accounts and completion ticks are not current acceptance or instructions.
   Entry banners route operators to this map; histories are retained, not rewritten as new results.
5. `engineering-delivery-closeout` delta requirements represent this unfinished candidate.
   Main specifications retain the published historical baseline until authorized completion
   and synchronization. Do not mistake an intentional active delta/main difference for
   permission to rewrite main specs or archive incomplete work.

`openspec` is unavailable on the current PATH. Manual structure/link/checksum checks are
E0 only; strict CLI validation remains BLOCKED. The three active changes remain independent:
engineering closeout, real CRM/mail/SSO integration, and UAT/grey rollout. The latter two
cannot be closed with reference-environment success.

## Remaining work and handover boundary

| Gate | Status | Evidence required before changing the status |
| --- | --- | --- |
| C24/C25 pushed full pytest | **FAIL (historical runs)** | Preserve original failure; local repair does not rewrite previous CI evidence |
| Local repaired full pytest | **PASS** | 871 tests + 225 subtests, zero skips; source-bound local receipt, macOS Python 3.13 |
| Repaired remote full pytest | **PASS** | `0d1a7ce`: Linux Python 3.11/3.13 each 872 tests + 225 subtests, zero skips |
| C10 lease-expiry write fencing | **OPEN** | Implement enforceable write ownership and verify late writers across actual processes/storage |
| L01–L16 / D01–D16 / O01–O16 / B01–B16 / S01–S16 / R01–R20 | **BLOCKED** | Exact isolated Linux candidate, independent services/observers, faults and each matrix's acceptance evidence |
| Real runtime and full RAG / historical credentials | **BLOCKED** | Actual store/model/identity/browser chain, fixed corpus/semantic review, separately authorized historical handling |
| CI image build, dependency imports and security scans | **PASS** | Run 39209313444 at `0d1a7ce`; CI-only image, not deployment acceptance |
| OpenSpec strict | **BLOCKED** | CLI unavailable; manual structure checks do not substitute for strict validation |
| C25 full reconciliation / engineering acceptance | **OPEN / BLOCKED** | Reconcile final accepted commit/image/runtime evidence, review and remaining P0/P1 issues |
| Enterprise UAT / grey / production | **BLOCKED** | Real resources, ownership, external contracts, observation and approval in their independent changes |

The authorized remote follow-up now covers scanner repair and subsequent CI failures.
C10 implementation repair and isolated runtime/strict-tooling acceptance remain separate
pending work. Do not merge, release, deploy, synchronize specs or archive. This increment
ends after reviewed follow-up results and waits for user confirmation.
