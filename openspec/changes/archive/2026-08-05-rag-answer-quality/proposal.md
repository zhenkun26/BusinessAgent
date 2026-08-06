## Why

RAG 检索链路指标已打满（22 条评测集，top1/3/5 命中率与 MRR 均为 1.0，见 `enterprise-agent/eval/results/latest.json`），但「检索到」不等于「答得对」：当前评测只统计 expected_keywords 在检索 chunk 中的出现比例，平均关键词覆盖率仅 0.606，即近四成关键事实没有进入上下文组装结果，更无法证明最终生成答案的准确性。同时 22 条样本只覆盖销售政策与财务报销两份文档，规模太小，不能代表真实企业多业务域知识库下的回答质量。按「真实生产上线」导向（见 `docs/40-process/优化方向分析-生产上线-2026-08-05.md`），答案准确性缺少度量基线与达标线是上线评审的 P0 缺口。

## What Changes

- **评测集扩充**：`enterprise-agent/eval/eval_set.json` 从 22 条扩充至 ≥100 条，覆盖多业务域（销售、财务、售后、人事、IT 等既有与新增知识文档），保留 scene（factual/policy/inferential）与 difficulty（easy/medium/hard）分层，并新增对抗性样本（库内无答案、诱导性表述、跨文档易混淆问题）。
- **失效模式分析**：对现有关键词覆盖率 < 1.0 的样本（latest.json 中 22 条里多数覆盖率为 0.5/0.667，Q018 为 0）逐条定位失效原因——检索命中但生成/组装漏关键词时，归因到 prompt 模板、上下文截断或 chunk 组装策略，形成分类统计与修复建议。
- **答案质量评测增强**：`eval/run_eval.py` 增加答案侧度量（生成答案对 expected_keywords 的覆盖率），区分「检索覆盖」与「答案覆盖」两层指标。
- **目标写入规格**：在 `knowledge-operations` 规格中新增答案质量评测需求——评测集规模下限、答案关键词覆盖率目标值、回归评测频率，作为后续 RAG 改动的验收基线。

## Capabilities

### New Capabilities

<!-- 无新增能力：评测与质量目标归属既有知识运营能力。 -->

### Modified Capabilities
- `knowledge-operations`: 新增答案质量评测相关需求——评测集规模与分层要求、答案关键词覆盖率目标值、失效模式分析要求与回归评测频率。

## Impact

- 评测资产：`enterprise-agent/eval/eval_set.json`（扩充至 ≥100 条）、`enterprise-agent/eval/run_eval.py`（新增答案侧覆盖率指标）、`enterprise-agent/eval/results/`（新评测基线报告）。
- 生成链路：`app/rag/`（prompt 模板与上下文组装策略，按失效模式分析结论修复）。
- 规格：`openspec/specs/knowledge-operations/spec.md` 经本 change 归档后新增答案质量评测需求。
- 知识库：扩充评测集可能需要向 `eval/sample_docs/` 补充多业务域样例文档。
