# FINANCE-QA-02 · Source and preservation ledger

[Reference review](reference-review.md) · [Scoring draft](scoring-rules.md) · [Exact session](session.md)

Documentation date: 2026-10-25, `America/New_York`. Static source/message inspection only; no application/scorer execution or independent annotation study.

## P · Financial-policy fixture

| Field | Binding / limit |
| --- | --- |
| Path | `enterprise-agent/eval/sample_docs/财务报销制度.md` |
| Inspected local revision | `372fcc367dfae969bd38e88194af010db18ed156`; original local branch has unpublished engineering ancestry, not uploaded by this increment |
| Git blob | `005c008cbb238b09b9af5d174aa55a3174f00fa5` |
| SHA-256 | `b781104c86183f631f7b761fd8d1b8b3fe4d44205e69bdb04927a8a1500ccd56` |
| Public counterpart | [Identical 89-line fixture at public revision 065bdf7](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/enterprise-agent/eval/sample_docs/财务报销制度.md) |
| Existing clause excerpts | [P-01–P-07 in the preserved original ledger](../2026-10-23-finance-qa-reference-set/sources.md#original-clause-excerpts); original text, line locators and header context unchanged |
| Effective policy version/date | UNKNOWN: fixture has no explicit effective date or policy version. Git/hash binds project bytes, not a real enterprise rule. |
| Scope | Only this supplied fixture supports the references. Full-text absence claims do not establish absence in other material; no policy-owner clarification or source-rights clearance is inferred. |

Current bytes equal the recorded local Git object and public-baseline object. The coaching's assistant full-text check is described in C1 messages at lines 524/533; the learner response at line 515 proposes a method and is not a receipt of learner-performed inspection.

## D · Original reference draft and learning record — preserved

D1 is the unchanged reference draft used during review: local revision `372fcc3`, [identical published reference at b735937](https://github.com/zhenkun26/BusinessAgent/blob/b7359371667d72abfe1a0cab4bc0f60a964deee8/BusinessAgent-workflow/runs/2026-10-23-finance-qa-reference-set/reference-set.md). Its Git blob is `74e60fbfe557593a7ea44d8133bd2511b424b3b6`.

| Local original file | SHA-256 | Availability / preservation limit |
| --- | --- | --- |
| `runs/2026-10-23-finance-qa-reference-set/reference-set.md` | `954b3ccf785e2959b443b137eb17f1d1344274a650ec864f5cf3b1a1a6f835de` | D1: local and pinned public bytes match; original seven reference blocks are copied verbatim into the new comparison document |
| `runs/2026-10-23-finance-qa-reference-set/session.md` | `f3ef24d54816c3c195b50237d2876cff311593e9b04a75c11211fa8afe411633` | Original local version retained; published session has explicitly declared link transformations and is not claimed byte-identical |
| `runs/2026-10-23-finance-qa-reference-set/sources.md` | `65ad2441140bc9799c66525ac85aef855cad9d2f29aac4145fba681776732be7` | Original local ledger retained; no replacement with later publication wording |

All three paths are relative to `BusinessAgent-workflow`. Their original local content/modes remain unchanged in the authoring checkout. The three previously published counterparts remain unchanged from `b735937`; the local session/ledger hashes above are not asserted to bind those transformed published versions. New “v1/v2” or “original/revised candidate” labels refer only to documentary drafts, not policy versions, evaluation-data releases or an adopted machine schema. Revised Chinese candidates are editorial renderings of the review, not verbatim learner answers.

## C1 · Original conversation — local-only

Conversation `01a167b9-4602-7662-acf6-25e2b71611bf`; local basename `rollout-2026-10-23T22-31-19-01a167b9-4602-7662-acf6-25e2b71611bf_01a16bbf-942c-7013-9605-95c7c0cf98f9.jsonl`. Selected original lines 417–699 contain the agenda and exercise, with all thirteen substantive learner responses. Both local date and UTC timestamps are retained in the session. The segment basename is older than this session; message timestamps, not the filename date, identify the review round.

The agenda at line 440 explicitly supplies coverage, unsupported additions/citations, over-refusal and denominator topics before the exercise. Include that prior framing when attributing later judgments. Thirty-three selected messages comprise two initial requests, thirteen learner responses, fifteen assistant final messages and three commentaries. Two machine-readable memory footers at lines 440/462 are omitted; original wording is otherwise preserved, with exactly eight assistant policy-link destinations adapted to the identical pinned public fixture as declared in the [publication view](session.md#fr-publication). The session digest binds only that declared selection/normalization.

C1 is a local log locator, not a public link. Full JSONL, private reasoning, tools, injected context and unrelated history are not copied or authorized for publication. Six original Markdown hard breaks (two trailing spaces) in assistant messages at lines 478, 492, 533 and 567 are retained as an explicit source-format exception; they are not stripped to silence the default whitespace checker.

Save request at C1 line 706 — original user message:

> 把这轮7题参考答案审校、最小判分规则和学习过程整理到 BusinessAgent-workflow，保留原稿、修订意见、制度版本、我的原始回答和你的追问，区分独立判断与提示后补充。先只整理文档，不改原评测集、不运行测试、不写代码、不开始重构。

That initial request authorized local documentation only. The subsequent explicit C2 instruction in this task authorizes selected document publication, preserving the original local branch and excluding engineering commits, merge, tests and reconstruction. Full raw logs remain unpublished.

C2 — subsequent publication instruction, original user message:

> 可以，把这轮参考答案审校、最小判分规则和学习记录也按之前的方式推送到纯文档分支，只包含 BusinessAgent-workflow 的文档改动，保留现有本地分支，不上传工程提交、不合并、不运行测试，也不开始重构。

## Protected evaluation and claim boundaries

- `enterprise-agent/eval/eval_set.json` retains SHA-256 `ae4304f0ed16263ea9d00cd1091435737e7a44a5c13b66dbee58bd1fa1437bcc`; no old question, Q015 annotation, scorer, C17 corpus/denominator or retained result is changed.
- FIN-01–FIN-07 remain document identifiers. The four hypothetical scoring candidates and timeout story are not additional dataset items or observed application outcomes. Existing FIN-N01 is linked as earlier synthetic material, not executed again.
- Source inspection, guided reference review and scoring proposals are distinct from independent reviewer agreement, actual model behavior, production acceptance and source-rights clearance. None of the latter is established here.
- The original reference and policy are inspectable through the pinned public counterparts above; unavailable local implementation records are not made public evidence by these documents. No new external research or upstream execution is claimed.
