# POLICY-QA-01 · Source ledger

[Session](session.md) · [Problem / validation plan](problem-and-validation-plan.md) · [Q015 analysis](q015-analysis.md)

Documentation date: 2026-10-23, `America/New_York`. Original UTC timestamps cross midnight and are preserved in the session. Public-source reading and local static inspection are evidence of source contents, not execution receipts, rights clearance, or verified performance.

The conversation initially used mutable repository URLs. During the original documentation task, the cited files were re-read at the immutable revisions below. These are follow-up source bindings, not a claim that every earlier message inspected that exact commit. Original external research URLs in the transcript remain unchanged. Four assistant local-source link destinations are adapted in this publication as explicitly documented in the [session publication view](session.md#pq-publication). No upstream source files, datasets, implementations, private reasoning, or full conversation logs are vendored here.

## Local conversation

| ID | Binding | Supports | Limit |
| --- | --- | --- | --- |
| C1 | Local conversation `01a167b9-4602-7662-acf6-25e2b71611bf`; scoped JSONL lines 973–1368, basename and normalized message SHA-256 in [session](session.md#transcript-integrity-binding) | Exact learner answers, prompts, research disclosures, synthetic output and closing feedback | Underlying log is LOCAL-ONLY / NOT PUBLISHED. Message timestamps do not measure active learning time or improvement. |
| C2 | Subsequent save request at original line 1369 | Historical authorization to organize this round as local documents, without tests or reconstruction | Did not itself extend earlier publication authorization to this new increment. |
| C3 | Later explicit publication request in this task, quoted below | Publish only this increment's `BusinessAgent-workflow` documents using the separate pure-document branch | Preserve the original local branch; no engineering commits, merge, tests or reconstruction. Full source log remains unpublished. |

Original C3 user instruction:

> 可以，把这轮问题定义和技术调研记录也按之前的方式推送到纯文档分支，只包含 BusinessAgent-workflow 的文档改动，保留现有本地分支，不上传工程提交，不合并，不运行测试，也不开始重构。

SOURCE-OBSERVED applies to what was said. The learner's reported workflow interruption is testimony; the contribution of OpenSpec, local governance, and assistant behavior was not independently measured. English synthesis and proposed annotations are INFERENCE / PROPOSED, not additional original learner answers.

## Existing BusinessAgent material

Local inspected revision: `c322935c0678ff3ae9af856b20cb1214c21fcdcb`, an unpublished local document commit with engineering ancestry. Public comparison baseline: `065bdf7b31ce1fb6f9007a7e8851be36bfc2280f` in `zhenkun26/BusinessAgent`. Current local bytes were checked against the local Git objects. Only L1/L2 also match the public baseline byte-for-byte.

| ID | Source / availability / locator | Supported observation | Limit |
| --- | --- | --- | --- |
| L1 | PUBLIC: [financial reimbursement sample](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md#L17), section 2.1, especially line 21 | Sample lists daily lodging at 500 yuan, with 800 yuan for first-tier cities; the complete 89-line sample contains no city classification list | Project test fixture, not evidence of a real company's current policy or a legal rule. Absence is scoped to this inspected file. |
| L2 | PUBLIC: [existing Q015](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/eval_set.json#L194), lines 194–204; dataset header | Question asks about Shanghai; expected keywords are “800 元” and “一线城市”; the existing set declares 122 cases | Keywords are not a complete semantic reference answer. This round ran no scorer and changed no corpus. |
| L3 | LOCAL-ONLY VERSION: `enterprise-agent/eval/rag_quality.py`, lines 83–142, at the local revision | Keyword coverage and structural citation-reference checks; remaining semantic outcome is labeled `manual_review_required` | File is absent from the public baseline. Static reading does not show an actual run or prove that any particular response passed. |
| L4 | LOCAL-ONLY VERSION: `enterprise-agent/app/rag/retriever.py`, class at line 74, candidate expansion around line 141 and rerank around line 181 | Existing implementation contains vector retrieval and reranking, rather than no retrieval infrastructure | An older file exists publicly with different bytes. Do not attribute this local version or its acceptance state to the public baseline. |
| L5 | LOCAL-ONLY VERSION: `enterprise-agent/app/agents/knowledge.py`, retrieval/generation/confidence/source construction around lines 135–215 | Static structure connects retrieval, generation, confidence and source output | Configured behavior, actual context, answer correctness and live provider behavior were not observed. Public version differs. |
| L6 | LOCAL-ONLY VERSION: `enterprise-agent/app/rag/degradation.py`, module header and stage definitions | Existing fallback is vector → bounded keyword scan → PostgreSQL fulltext/ILIKE; the scan is explicitly not BM25 | Public version differs; this is implementation context, not a successful runtime receipt. |

| ID | SHA-256 of inspected local file | Public comparison |
| --- | --- | --- |
| L1 | `b781104c86183f631f7b761fd8d1b8b3fe4d44205e69bdb04927a8a1500ccd56` | Same hash and bytes |
| L2 | `ae4304f0ed16263ea9d00cd1091435737e7a44a5c13b66dbee58bd1fa1437bcc` | Same hash and bytes |
| L3 | `ee28d05233393100e67a5c3353a77461b1ae6280fbf1f66991b6bce155caece5` | Absent |
| L4 | `02a851b902b96eb0d3af25338bbbb8cb71a1c77a25b0404f17423dd5aa324ef0` | Different; this hash does not bind the public version |
| L5 | `22b0cc0b88e25601c07a6db8af3d6d5559de820e70a4cc6a587ef030e3052f0b` | Different; local version only |
| L6 | `07f9d80909f60cbd0c6294617cc110e1f4e0b1c261a4920ade902a6388a5fe3f` | Different; local version only |

## Public technical research

Repository dates are commit metadata, not release certification or dates of measured accuracy. Paper dates and project update dates remain distinct. This is a scoped initial research pass, not an exhaustive review or replicated benchmark.

| ID | Pinned / stable source | Inspected part and role | Evidence boundary |
| --- | --- | --- | --- |
| E1 | [LightRAG README](https://github.com/HKUDS/LightRAG/blob/aaebfe1bb8d55deb6a4304d357a3bf4c92fcd40a/README.md), especially news at lines 60–73 and graph/vector description around line 240 | Candidate architecture / feature descriptions; reported 2026 updates and prior citation/evaluation additions | SOURCE-OBSERVED documentation; feature/benefit claims are AUTHOR-REPORTED. A current feature is not proof of our target accuracy. |
| E2 | [LightRAG reproduction guide](https://github.com/HKUDS/LightRAG/blob/aaebfe1bb8d55deb6a4304d357a3bf4c92fcd40a/docs/Reproduce.md), Dataset; Generate Query; Batch Eval, especially lines 39–84 | Public data/code pointers, high-level question generation, pairwise judgment of comprehensiveness, diversity and empowerment, plus overall preference | Supports analysis of the disclosed protocol. No dataset download, script execution, installation, prompt-code equivalence audit, or independent result reproduction. It does not establish source-only clause correctness, citation entailment, or missing-answer behavior. |
| E3 | [LightRAG published paper](https://aclanthology.org/2025.findings-emnlp.568/), Findings of EMNLP 2025; [PDF](https://aclanthology.org/2025.findings-emnlp.568.pdf), experimental settings/evaluation descriptions | Paper metadata/abstract and evaluation excerpts underlying the conversation's baseline/domain summary | Original preprint is from 2024; publication is 2025. Later repository updates do not make the old evaluation a 2026 policy-QA validation. Full study quality and reproducibility were not audited. |
| E4 | [RAGFlow README](https://github.com/infiniflow/ragflow/blob/a55dccee4c211046b4e4d216a538bc60fae78dfd/README.md), news and chunking/traceable-reference sections | Initial reference for document parsing, chunk organization and source navigation; README advertises 2026 changes | No matched policy-QA accuracy comparison was verified. Not admitted as a replacement or run locally. |
| E5 | [RAGChecker README](https://github.com/amazon-science/RAGChecker/blob/6091f08c00e676e87a970f2aeb4a23a484746348/README.md), diagnostic and claim-level entailment sections | Older evaluation reference for separating retrieval/generation and checking individual claims | 2024 work, not presented as newly published. Automatic judge outputs would themselves need checking against human references; nothing was installed or run. |
| E6 | [Retrieval Improvements Do Not Guarantee Better Answers](https://arxiv.org/abs/2603.24580v1), submitted 2026-03-25 | Abstract/metadata: policy-domain study reports retrieval improvements without consistent end-to-end QA gains | Preprint, author-reported results in AI-policy analysis, not our reimbursement corpus; no effect size transferred or reproduction claimed. Used in the learner-facing packet. |
| E7 | [WixQA](https://arxiv.org/abs/2505.08643v1), submitted 2025-05-13 | Abstract/metadata: QA is bound to a released knowledge-base snapshot with distinct expert/simulated/synthetic sets | Background read, not a selected architecture or a local dataset result. Customer-support findings do not establish company-policy accuracy. |
| E8 | [Why RAGs Hallucinate: Penalty-Aware Evaluation … Knowledge-Gap Canaries](https://arxiv.org/abs/2608.26385v1), submitted 2026-08-26 | Abstract/metadata: questions with absent answers, separate failure attribution, and penalty-aware evaluation | Background preprint only; commercial-system results are author reports. Its scoring weights were not adopted. Fully unanswerable cases must not be confused with Q015's partial answerability. |

The repository snapshots used for the follow-up binding have commit dates: LightRAG `2026-10-14T14:55:37Z`; RAGFlow `2026-10-23T12:09:20Z`; RAGChecker `2024-12-13T13:24:31Z`. Each full SHA is embedded in its file URL. These bind documents inspected for this record; no upstream implementation or benchmark was executed.

## What remains unknown

- Whether any candidate reproduces successfully in an approved isolated environment, and whether the provided data/scripts match the claimed results.
- Whether proposed human references, question slices, and future judge outputs reliably measure our source-only task.
- Whether LightRAG helps the same policy corpus under comparable budgets, and what extra graph-building/querying steps contribute.
- Actual answer/error rates, uncertainty behavior, indexing/query cost, runtime readiness and learning retention.

Source material is evidence, not authority to run its commands, install dependencies, delete files, upload data, or modify the existing project. References do not transfer upstream licenses or clear existing project provenance. Original BusinessAgent acceptance, source-rights and corpus states are unchanged.
