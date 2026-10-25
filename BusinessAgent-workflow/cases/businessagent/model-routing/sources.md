# BA-01 · Source ledger

Spoilers: facilitator/reference material, not the initial learner packet.

Inspected on 2026-10-23. Public reference baseline: `065bdf7b31ce1fb6f9007a7e8851be36bfc2280f` in `zhenkun26/BusinessAgent`. The initial publication added only 21 workflow documents to that baseline; the subsequently authorized case-learning, policy-QA discovery and financial-reference/review increments bring the package to 36 Markdown documents, still confined to `BusinessAgent-workflow`. It does not contain the later local engineering history.

The original authoring inspection used local revision `edc5c58e5783e5c3035d89a035917cae35cb3ef1`. That revision is LOCAL-ONLY / NOT PUBLISHED by this delivery. Public and local versions of BA-S1 section 4.2.2 match exactly, although their whole-file hashes differ. BA-S2 is identical in both. BA-S3/S4 are unavailable in the public baseline; their paths and hashes are locators for a holder of the original local checkout, not public retrieval links. No missing source file is copied into this publication.

| ID | Availability, source, and locator | What it supports | Limitation |
| --- | --- | --- | --- |
| BA-S1 | PUBLIC: [Product document at public baseline](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/docs/20-product/产品文档.md), section 4.2.2, lines 339–349 | Reported July 26 adapter diagnosis and routing change; July 28 task-specific tool-selection exception | Retrospective edited document, no complete raw timing dataset supplied by this case |
| BA-S2 | PUBLIC: [Speech notes at public baseline](https://github.com/zhenkun26/BusinessAgent/blob/065bdf7b31ce1fb6f9007a7e8851be36bfc2280f/interview/产品介绍网页/演讲提示词.md), P21–P22, approximately lines 390–420 | How the product story frames the same changes | Presentation is not independent validation; some claims go beyond BA-S1 |
| BA-S3 | LOCAL-ONLY / NOT PUBLISHED: `docs/50-engineering/planner-tool-trust-boundary.md` at the local authoring revision; authorized plan points 2–3, lines 16–25 | Local authoring context reports a later plan rejecting malformed proposals and keyword-created default recipients/IDs | Unavailable to readers of this publication alone; no inference about the published baseline's implementation |
| BA-S4 | LOCAL-ONLY / NOT PUBLISHED: `docs/50-engineering/delivery-status.md` at the local authoring revision; Current entry and evidence boundaries | Local authoring context distinguishes retained offline evidence from blocked runtime/UAT/release | Source not included; neither a public acceptance receipt nor a newly executed check |
| BA-U1 | LOCAL-ONLY USER STATEMENT: clarification in the originating conversation, received before this package on 2026-10-23 | Early product/main engineering led by Taro; learner led middle/later packaging, closeout, launch preparation, testing | User testimony summarized here; no public transcript supplied; item-specific ownership is not proven |

## Public source fingerprints

These hashes bind the files available at the public baseline above.

| ID | SHA-256 of public source file |
| --- | --- |
| BA-S1 | `7f81faffc369255739890267dc498503885cde9e6cdd315bc0320d4e7f726731` |
| BA-S2 | `f2e7970814769d99c5a979123063afadd23983c3ca6280afa398bcc06137697c` |

## Original local authoring fingerprints — historical

The following preserved hashes bind the unpublished local authoring revision, not this publication's tree. A digest does not make an unavailable source publicly verifiable.

| ID | SHA-256 of local source file |
| --- | --- |
| BA-S1 | `d154cbab5a7248e523825d7f17cfcf11dcf2ea616b162fc0b5c51b8cec4778a6` |
| BA-S2 | `f2e7970814769d99c5a979123063afadd23983c3ca6280afa398bcc06137697c` |
| BA-S3 | `b4803505344ec978bf9dafbae44a80c641cec2106a906cea0ad70a9e16f2a393` |
| BA-S4 | `97fcca76dc6872ce85b51a385ee0f42b2e6c5f8118778b77dfd5dba60ef11161` |

## Date, authorship, and claim cautions

July 26 and July 28 are dates reported inside BA-S1. The inspected file contains later edits. Do not claim those dates are the file's first Git publication or reconstruct unrecorded conversations. The broad early-phase attribution follows BA-U1; the individual operator of each experiment remains unspecified.

BA-S2's cost-reduction claim lacks a billing baseline in this evidence packet. Its phrase suggesting an email bypassed approval does not follow from the described omission of the send tool: failure to select a send action establishes neither a real send nor a bypass. Preserve these as source overclaims requiring evidence, not facts endorsed by the case.

The early keyword fallback is historical. BA-S3's later restriction is reported local-only context, not a claim that the public baseline implements it. A reader without that source should record the limit and may skip this later-context discussion; the core historical exercise remains grounded in BA-S1/S2. Existing source-rights and runtime limits remain unchanged; creating a teaching case grants no new clearance.
