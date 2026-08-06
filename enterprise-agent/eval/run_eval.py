"""RAG 评测脚本(对应 v3 方案 W4 验收;rag-answer-quality 变更增加答案层评测)

用法:
    # 1. 自动入库 + 评测(memory 后端,无需 Docker)
    python -m eval.run_eval --ingest

    # 2. 仅评测(假设 VectorStore 已有数据)
    python -m eval.run_eval

    # 3. 重建 VectorStore 后评测(milvus 后端,会清空数据)
    python -m eval.run_eval --ingest --recreate

    # 4. 只做检索层评测(跳过 LLM 生成,快速回归检索指标)
    python -m eval.run_eval --no-answer

评测指标(两层,见 openspec change rag-answer-quality):
- 检索层:Top-K 命中率(K=1/3/5)、MRR、关键词覆盖率(expected_keywords
  在 Top-K content 中的出现比例)、分场景/分难度统计
- 答案层:对每条样本经 `app/rag` 生成链路(knowledge_rag_answer prompt + lite LLM)
  生成答案,统计 expected_keywords 在最终答案中的覆盖率;生成失败的样本标记
  answer_status=failed,不计入答案层覆盖率分子分母
- 对抗样本(expected_behavior=refuse/clarify)单独统计拒答/澄清命中率,
  不计入答案层覆盖率分子分母;判定口径为答案中包含拒答/澄清特征词
  (design Open Questions 第 1 条:以生成行为为准)
- 逐样本诊断:检索命中情况、进入上下文的内容(top_k_chunks[].content)、
  生成答案(answer)与失效模式分类(failure_mode:retrieval_miss /
  assembly_omission / generation_omission),支撑失效归因

验收标准:Top-5 命中率 ≥ 85% 且答案层平均关键词覆盖率 ≥ 85%
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from loguru import logger

# 让 `python -m eval.run_eval` 能找到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.rag.retriever import EnterpriseRAGRetriever  # noqa: E402
from app.rag.vector_store import get_vector_store, reset_vector_store  # noqa: E402

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"


@dataclass
class SampleResult:
    """单条样本评测结果(含检索层 + 答案层 + 逐样本诊断)"""

    query_id: str
    query: str
    ground_truth_doc: str
    ground_truth_section: str
    expected_keywords: list[str]
    scene: str
    difficulty: str
    # 对抗样本预期行为:"answer"(默认) | "refuse"(拒答) | "clarify"(澄清)
    expected_behavior: str = "answer"
    # 检索结果(含进入上下文的内容,支撑失效归因)
    top_k_chunks: list[dict] = field(default_factory=list)  # [{title, score, doc_match, content}]
    # 检索层指标
    hit_at_1: bool = False
    hit_at_3: bool = False
    hit_at_5: bool = False
    first_hit_rank: int = 0  # 0 表示未命中
    reciprocal_rank: float = 0.0
    keyword_coverage: float = 0.0
    top_score: float = 0.0
    latency_ms: int = 0
    # 答案层结果(answer_status: ok / failed / skipped)
    answer_status: str = "skipped"
    answer: str = ""
    answer_keyword_coverage: float = 0.0
    answer_keywords_hit: list[str] = field(default_factory=list)
    answer_keywords_missed: list[str] = field(default_factory=list)
    # 对抗样本判定:答案中是否检测到预期行为(拒答/澄清)特征词
    behavior_detected: bool = False
    # 失效模式分类:"" | retrieval_miss | assembly_omission | generation_omission
    failure_mode: str = ""


@dataclass
class EvalReport:
    """评测总报告(检索层 + 答案层)"""

    total: int
    top1_hit_rate: float
    top3_hit_rate: float
    top5_hit_rate: float
    mrr: float
    avg_keyword_coverage: float
    avg_latency_ms: float
    # 答案层:仅统计 answer_status=ok 且 expected_behavior=answer 的样本
    avg_answer_keyword_coverage: float = 0.0
    answer_evaluated: int = 0  # 计入答案层覆盖率的样本数
    answer_failed: int = 0  # 生成失败(不计入分子分母)
    # 对抗样本(expected_behavior=refuse/clarify)行为命中率
    adversarial_total: int = 0
    adversarial_correct: int = 0
    # 失效模式分类统计(retrieval_miss / assembly_omission / generation_omission)
    failure_mode_stats: dict[str, int] = field(default_factory=dict)
    by_scene: dict[str, dict] = field(default_factory=dict)
    by_difficulty: dict[str, dict] = field(default_factory=dict)
    samples: list[SampleResult] = field(default_factory=list)


# 对抗样本判定口径(design Open Questions 第 1 条):以答案中包含拒答/澄清
# 特征词为准——系统应先检索再据上下文判断,而不是要求检索层不命中
REFUSAL_MARKERS = [
    "未在知识库中找到",
    "知识库未覆盖",
    "未覆盖该情形",
    "未收录",
    "没有相关信息",
    "无相关信息",
    "无法回答",
    "无法基于",
    "不足以回答",
    "没有找到",
]
CLARIFY_MARKERS = [
    "请补充",
    "请明确",
    "请提供更多信息",
    "请说明",
    "澄清",
    "指的是哪",
    "能否具体",
]


def compute_keyword_coverage(text: str, keywords: list[str]) -> tuple[float, list[str], list[str]]:
    """关键词覆盖率机械口径:返回 (覆盖率, 命中词, 遗漏词);大小写不敏感"""
    if not keywords:
        return 0.0, [], []
    lowered = text.lower()
    hit = [kw for kw in keywords if kw.lower() in lowered]
    missed = [kw for kw in keywords if kw.lower() not in lowered]
    return len(hit) / len(keywords), hit, missed


def detect_expected_behavior(answer: str, expected_behavior: str) -> bool:
    """对抗样本行为判定:拒答样本看拒答特征词,澄清样本看澄清特征词"""
    markers = CLARIFY_MARKERS if expected_behavior == "clarify" else REFUSAL_MARKERS
    return any(m in answer for m in markers)


def classify_failure_mode(sr: SampleResult) -> str:
    """失效模式三分类(仅对正常作答样本;对抗样本不参与)

    - retrieval_miss: 检索未命中(Top-5 无 ground_truth_doc)
    - assembly_omission: 检索命中但 expected_keywords 未全部进入 Top-5 上下文
    - generation_omission: 关键词已在上下文中但最终答案遗漏(生成/prompt 问题)
    """
    if sr.expected_behavior != "answer":
        return ""
    if not sr.hit_at_5:
        return "retrieval_miss"
    if sr.keyword_coverage < 1.0:
        return "assembly_omission"
    if sr.answer_status == "ok" and sr.answer_keyword_coverage < 1.0:
        return "generation_omission"
    return ""


async def generate_answer(query: str, chunks: list[dict]) -> str:
    """调用生成链路(knowledge_rag_answer prompt + lite LLM)生成答案

    与 KnowledgeAgent._generate_answer 同源的精简版:上下文构造与 prompt 一致,
    不含自评与置信度决策(评测只需要最终答案文本)。
    """
    from langchain_core.prompts import ChatPromptTemplate

    from app.prompts import get_prompt
    from app.rag.llm import get_lite_llm

    context = "\n\n".join(
        f"[片段{i}] {c['title']}\n{c['content']}" for i, c in enumerate(chunks, start=1)
    )
    tpl, _pv = get_prompt("knowledge_rag_answer")
    prompt = ChatPromptTemplate.from_template(tpl)
    resp = await (prompt | get_lite_llm()).ainvoke({"context": context, "query": query})
    return resp.content if hasattr(resp, "content") else str(resp)


def load_eval_set(path: Path | None = None) -> dict:
    eval_set_path = path or EVAL_SET_PATH
    if not eval_set_path.exists():
        raise FileNotFoundError(f"评测集不存在: {eval_set_path}")
    with open(eval_set_path, encoding="utf-8") as f:
        return json.load(f)


async def ensure_ingest(recreate: bool = False) -> dict:
    """自动入库 sample_docs(若 VectorStore 为空)"""
    settings = get_settings()

    # Milvus 后端需先 init
    if settings.vector_store_provider.lower() == "milvus":
        from app.core.milvus_client import init_milvus

        await init_milvus(recreate=recreate)
    elif recreate:
        # memory 后端:重置单例即清空
        reset_vector_store()

    # 检查是否已有数据
    vs = get_vector_store()
    stats_before = vs.get_stats()
    logger.info(f"入库前 VectorStore 状态: {stats_before}")

    if stats_before.get("total_entities", 0) > 0 and not recreate:
        logger.info("VectorStore 已有数据,跳过入库")
        return stats_before

    # 入库
    from app.rag.ingest import MilvusIngestService

    service = MilvusIngestService(vector_store=vs)
    stats = await service.ingest_directory(
        dir_path=SAMPLE_DOCS_DIR,
        doc_type="policy",
        dept_namespace="shared_company",
    )
    logger.info(f"入库完成: {stats}")
    logger.info(f"入库后 VectorStore 状态: {vs.get_stats()}")
    return vs.get_stats()


def evaluate_single(
    retriever: EnterpriseRAGRetriever,
    sample: dict,
    user_role: str = "admin",
) -> SampleResult:
    """评测单条样本"""
    sr = SampleResult(
        query_id=sample["query_id"],
        query=sample["query"],
        ground_truth_doc=sample["ground_truth_doc"],
        ground_truth_section=sample.get("ground_truth_section", ""),
        expected_keywords=sample.get("expected_keywords", []),
        scene=sample.get("scene", "factual"),
        difficulty=sample.get("difficulty", "medium"),
        expected_behavior=sample.get("expected_behavior", "answer"),
    )

    # 检索
    try:
        result = retriever.retrieve(
            query=sample["query"],
            user_role=user_role,
            dept_namespace="shared_company",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"检索失败 {sample['query_id']}: {e}")
        return sr

    sr.latency_ms = result.latency_ms
    sr.top_score = result.top_score

    # Top-K 命中判断:检索结果中是否有 chunk 来自 ground_truth_doc
    # (对抗样本无 ground_truth_doc,空串不参与匹配,否则 "" in title 恒真)
    ground_truth_doc = sample["ground_truth_doc"]
    for rank, chunk in enumerate(result.results, start=1):
        doc_match = bool(ground_truth_doc) and (
            chunk.title == ground_truth_doc or ground_truth_doc in chunk.title
        )
        sr.top_k_chunks.append(
            {
                "rank": rank,
                "title": chunk.title,
                "score": chunk.score,
                "doc_match": doc_match,
                # 进入上下文的内容(逐样本诊断,支撑失效归因)
                "content": chunk.content,
            }
        )
        if doc_match:
            if sr.first_hit_rank == 0:
                sr.first_hit_rank = rank
                sr.reciprocal_rank = 1.0 / rank
            if rank == 1:
                sr.hit_at_1 = True
            if rank <= 3:
                sr.hit_at_3 = True
            if rank <= 5:
                sr.hit_at_5 = True

    # 关键词覆盖率:expected_keywords 在 Top-5 content 中的出现比例
    top5_text = " ".join(c["content"] for c in sr.top_k_chunks[:5])
    sr.keyword_coverage, _, _ = compute_keyword_coverage(top5_text, sr.expected_keywords)

    return sr


async def evaluate_answer(sr: SampleResult) -> SampleResult:
    """答案层评测:生成答案 → 覆盖率 / 对抗行为判定 → 失效模式分类

    生成失败的样本标记 answer_status=failed,不计入覆盖率分子分母。
    """
    # 生成上下文与线上链路一致:取精排后的 Top-N(即检索返回的全部结果)
    chunks = sr.top_k_chunks
    if not chunks:
        if sr.expected_behavior != "answer":
            # 对抗样本检索为空时,线上链路直接返回固定拒答文案(不调 LLM),
            # 评测复现同一行为再按特征词判定
            sr.answer = "未在知识库中找到相关信息。"
            sr.answer_status = "ok"
            sr.behavior_detected = detect_expected_behavior(sr.answer, sr.expected_behavior)
        else:
            # 无检索结果时不调用 LLM,视为检索未命中,标记跳过
            sr.answer_status = "skipped"
        sr.failure_mode = classify_failure_mode(sr)
        return sr
    try:
        sr.answer = await generate_answer(sr.query, chunks)
        sr.answer_status = "ok"
    except Exception as e:  # noqa: BLE001
        logger.error(f"答案生成失败 {sr.query_id}: {e}")
        sr.answer_status = "failed"
        sr.failure_mode = classify_failure_mode(sr)
        return sr

    if sr.expected_behavior == "answer":
        cov, hit, missed = compute_keyword_coverage(sr.answer, sr.expected_keywords)
        sr.answer_keyword_coverage = cov
        sr.answer_keywords_hit = hit
        sr.answer_keywords_missed = missed
    else:
        # 对抗样本:按预期行为(拒答/澄清)特征词判定,不计入覆盖率
        sr.behavior_detected = detect_expected_behavior(sr.answer, sr.expected_behavior)
    sr.failure_mode = classify_failure_mode(sr)
    return sr


async def _run_answer_phase(results: list[SampleResult]) -> None:
    """在同一事件循环内逐条执行答案层评测(LLM 单例客户端绑定首个 loop)"""
    for sr in results:
        await evaluate_answer(sr)


def aggregate_report(results: list[SampleResult]) -> EvalReport:
    """汇总评测报告(检索层 + 答案层)"""
    total = len(results)
    if total == 0:
        return EvalReport(
            total=0,
            top1_hit_rate=0,
            top3_hit_rate=0,
            top5_hit_rate=0,
            mrr=0,
            avg_keyword_coverage=0,
            avg_latency_ms=0,
        )

    # 检索层命中率/MRR 只统计有 ground_truth_doc 的样本
    # (无答案对抗样本无真值文档,hit@k 对其无定义)
    rated = [r for r in results if r.ground_truth_doc]
    n_rated = len(rated)
    top1 = sum(1 for r in rated if r.hit_at_1) / n_rated if n_rated else 0.0
    top3 = sum(1 for r in rated if r.hit_at_3) / n_rated if n_rated else 0.0
    top5 = sum(1 for r in rated if r.hit_at_5) / n_rated if n_rated else 0.0
    mrr = sum(r.reciprocal_rank for r in rated) / n_rated if n_rated else 0.0
    # 关键词覆盖率只统计有 expected_keywords 的样本(对抗样本无关键词,不计入)
    kw_rated = [r for r in results if r.expected_keywords]
    kw_cov = sum(r.keyword_coverage for r in kw_rated) / len(kw_rated) if kw_rated else 0.0
    avg_lat = sum(r.latency_ms for r in results) / total

    # 答案层:只统计正常作答且生成成功的样本;对抗样本与生成失败样本不计入分子分母
    answer_ok = [r for r in results if r.expected_behavior == "answer" and r.answer_status == "ok"]
    answer_failed = sum(1 for r in results if r.answer_status == "failed")
    avg_answer_cov = (
        sum(r.answer_keyword_coverage for r in answer_ok) / len(answer_ok) if answer_ok else 0.0
    )

    # 对抗样本:行为命中率
    adversarial = [r for r in results if r.expected_behavior != "answer"]
    adversarial_correct = sum(1 for r in adversarial if r.behavior_detected)

    # 失效模式分类统计(仅正常作答样本)
    failure_stats: dict[str, int] = {}
    for r in results:
        if r.failure_mode:
            failure_stats[r.failure_mode] = failure_stats.get(r.failure_mode, 0) + 1

    # 分场景
    by_scene: dict[str, dict] = {}
    for scene in ["factual", "policy", "inferential"]:
        subset = [r for r in results if r.scene == scene]
        if subset:
            scene_rated = [r for r in subset if r.ground_truth_doc]
            scene_answer_ok = [
                r for r in subset if r.expected_behavior == "answer" and r.answer_status == "ok"
            ]
            scene_kw = [r for r in subset if r.expected_keywords]
            by_scene[scene] = {
                "total": len(subset),
                "top5_hit_rate": (
                    sum(1 for r in scene_rated if r.hit_at_5) / len(scene_rated)
                    if scene_rated
                    else 0.0
                ),
                "mrr": (
                    sum(r.reciprocal_rank for r in scene_rated) / len(scene_rated)
                    if scene_rated
                    else 0.0
                ),
                "keyword_coverage": (
                    sum(r.keyword_coverage for r in scene_kw) / len(scene_kw) if scene_kw else 0.0
                ),
                "answer_keyword_coverage": (
                    sum(r.answer_keyword_coverage for r in scene_answer_ok) / len(scene_answer_ok)
                    if scene_answer_ok
                    else None
                ),
            }

    # 分难度
    by_diff: dict[str, dict] = {}
    for diff in ["easy", "medium", "hard"]:
        subset = [r for r in results if r.difficulty == diff]
        if subset:
            diff_rated = [r for r in subset if r.ground_truth_doc]
            diff_answer_ok = [
                r for r in subset if r.expected_behavior == "answer" and r.answer_status == "ok"
            ]
            diff_kw = [r for r in subset if r.expected_keywords]
            by_diff[diff] = {
                "total": len(subset),
                "top5_hit_rate": (
                    sum(1 for r in diff_rated if r.hit_at_5) / len(diff_rated)
                    if diff_rated
                    else 0.0
                ),
                "mrr": (
                    sum(r.reciprocal_rank for r in diff_rated) / len(diff_rated)
                    if diff_rated
                    else 0.0
                ),
                "keyword_coverage": (
                    sum(r.keyword_coverage for r in diff_kw) / len(diff_kw) if diff_kw else 0.0
                ),
                "answer_keyword_coverage": (
                    sum(r.answer_keyword_coverage for r in diff_answer_ok) / len(diff_answer_ok)
                    if diff_answer_ok
                    else None
                ),
            }

    return EvalReport(
        total=total,
        top1_hit_rate=top1,
        top3_hit_rate=top3,
        top5_hit_rate=top5,
        mrr=mrr,
        avg_keyword_coverage=kw_cov,
        avg_latency_ms=avg_lat,
        avg_answer_keyword_coverage=avg_answer_cov,
        answer_evaluated=len(answer_ok),
        answer_failed=answer_failed,
        adversarial_total=len(adversarial),
        adversarial_correct=adversarial_correct,
        failure_mode_stats=failure_stats,
        by_scene=by_scene,
        by_difficulty=by_diff,
        samples=results,
    )


def print_report(
    report: EvalReport, target_top5: float = 0.85, target_answer: float = 0.85
) -> None:
    """打印评测报告(检索层 + 答案层 + 失效模式统计)"""
    print("\n" + "=" * 60)
    print("📊 RAG 评测报告")
    print("=" * 60)
    print(f"样本总数: {report.total}")
    print(f"Top-1 命中率: {report.top1_hit_rate:.2%}")
    print(f"Top-3 命中率: {report.top3_hit_rate:.2%}")
    print(f"Top-5 命中率: {report.top5_hit_rate:.2%}  (目标 ≥ {target_top5:.0%})")
    print(f"MRR:         {report.mrr:.4f}")
    print(f"检索层关键词覆盖率: {report.avg_keyword_coverage:.2%}")
    print(f"平均延迟:    {report.avg_latency_ms:.0f} ms")

    print("\n--- 答案层 ---")
    if report.answer_evaluated:
        print(
            f"答案层关键词覆盖率: {report.avg_answer_keyword_coverage:.2%}  "
            f"(目标 ≥ {target_answer:.0%},计入 {report.answer_evaluated} 条,"
            f"生成失败 {report.answer_failed} 条不计入)"
        )
    else:
        print("答案层未评测(--no-answer 或全部生成失败)")
    if report.adversarial_total:
        print(
            f"对抗样本行为命中率: {report.adversarial_correct}/{report.adversarial_total}"
            " (拒答/澄清特征词口径)"
        )
    if report.failure_mode_stats:
        stats = ", ".join(f"{k}={v}" for k, v in sorted(report.failure_mode_stats.items()))
        print(f"失效模式统计: {stats}")

    print("\n--- 分场景 ---")
    for scene, s in report.by_scene.items():
        ans = s.get("answer_keyword_coverage")
        ans_str = f"{ans:.2%}" if ans is not None else "N/A"
        print(
            f"  {scene:12s}  n={s['total']:2d}  Top5={s['top5_hit_rate']:.2%}  "
            f"MRR={s['mrr']:.4f}  检索覆盖={s['keyword_coverage']:.2%}  答案覆盖={ans_str}"
        )

    print("\n--- 分难度 ---")
    for diff, s in report.by_difficulty.items():
        ans = s.get("answer_keyword_coverage")
        ans_str = f"{ans:.2%}" if ans is not None else "N/A"
        print(
            f"  {diff:8s}  n={s['total']:2d}  Top5={s['top5_hit_rate']:.2%}  "
            f"MRR={s['mrr']:.4f}  检索覆盖={s['keyword_coverage']:.2%}  答案覆盖={ans_str}"
        )

    # 验收
    print("\n" + "=" * 60)
    top5_ok = report.top5_hit_rate >= target_top5
    answer_ok = report.answer_evaluated == 0 or report.avg_answer_keyword_coverage >= target_answer
    if top5_ok and answer_ok:
        print(f"✅ 验收通过: Top-5 命中率 {report.top5_hit_rate:.2%} ≥ {target_top5:.0%}")
        if report.answer_evaluated:
            print(
                f"✅ 答案层达标: 覆盖率 {report.avg_answer_keyword_coverage:.2%} "
                f"≥ {target_answer:.0%}"
            )
    else:
        if not top5_ok:
            gap = target_top5 - report.top5_hit_rate
            print(f"❌ 检索层未通过: Top-5 命中率 {report.top5_hit_rate:.2%},差 {gap:.2%}")
        if not answer_ok:
            gap = target_answer - report.avg_answer_keyword_coverage
            print(f"❌ 答案层未通过: 覆盖率 {report.avg_answer_keyword_coverage:.2%},差 {gap:.2%}")
        # 输出未命中样本
        missed = [s for s in report.samples if not s.hit_at_5]
        if missed:
            print(f"\n未命中样本({len(missed)} 条):")
            for s in missed[:10]:
                print(f"  [{s.query_id}] {s.query[:60]}")
                print(f"    ground_truth={s.ground_truth_doc} / {s.ground_truth_section}")
                if s.top_k_chunks:
                    print(
                        f"    实际 Top-3: {[(c['title'], round(c['score'], 3)) for c in s.top_k_chunks[:3]]}"
                    )
    print("=" * 60)


def save_report_json(report: EvalReport, output_path: Path) -> None:
    """保存 JSON 报告(检索层既有字段保持兼容,新增答案层字段并列)"""
    data = {
        "total": report.total,
        "top1_hit_rate": report.top1_hit_rate,
        "top3_hit_rate": report.top3_hit_rate,
        "top5_hit_rate": report.top5_hit_rate,
        "mrr": report.mrr,
        "avg_keyword_coverage": report.avg_keyword_coverage,
        "avg_latency_ms": report.avg_latency_ms,
        # 答案层(新增)
        "avg_answer_keyword_coverage": report.avg_answer_keyword_coverage,
        "answer_evaluated": report.answer_evaluated,
        "answer_failed": report.answer_failed,
        "adversarial_total": report.adversarial_total,
        "adversarial_correct": report.adversarial_correct,
        "failure_mode_stats": report.failure_mode_stats,
        "by_scene": report.by_scene,
        "by_difficulty": report.by_difficulty,
        "samples": [asdict(s) for s in report.samples],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"报告已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="RAG 评测脚本")
    parser.add_argument("--ingest", action="store_true", help="评测前自动入库 sample_docs")
    parser.add_argument("--recreate", action="store_true", help="重建 VectorStore(清空数据)")
    parser.add_argument("--top-k", type=int, default=10, help="粗排 Top-K(默认 10)")
    parser.add_argument("--rerank-n", type=int, default=5, help="精排 Top-N(默认 5)")
    parser.add_argument(
        "--rerank",
        choices=["auto", "local_bge", "llm", "passthrough"],
        default="auto",
        help="精排策略: auto=按 .env RERANKER_PROVIDER; "
        "local_bge=本地 bge-reranker-large(推荐); "
        "llm=本地 ollama 打分(慢); "
        "passthrough=不重排(快)",
    )
    parser.add_argument("--target", type=float, default=0.85, help="Top-5 命中率目标(默认 0.85)")
    parser.add_argument(
        "--answer-target",
        type=float,
        default=0.85,
        help="答案层平均关键词覆盖率目标(默认 0.85,见 knowledge-operations 规格)",
    )
    parser.add_argument(
        "--with-answer",
        dest="with_answer",
        action="store_true",
        default=True,
        help="启用答案层评测(默认开启,需 LLM 可用)",
    )
    parser.add_argument(
        "--no-answer",
        dest="with_answer",
        action="store_false",
        help="只做检索层评测(跳过 LLM 生成,快速回归检索指标)",
    )
    parser.add_argument(
        "--eval-set",
        type=str,
        default=None,
        help="评测集路径(默认 eval/eval_set.json;失效归因时可指向旧版小集)",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="JSON 报告输出路径(默认 eval/results/latest.json)"
    )
    args = parser.parse_args()

    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    # 加载评测集
    eval_set = load_eval_set(Path(args.eval_set) if args.eval_set else None)
    samples = eval_set["samples"]
    print(f"加载评测集: {len(samples)} 条样本")

    # 入库(如需要)
    if args.ingest:
        asyncio.run(ensure_ingest(recreate=args.recreate))
    elif get_settings().vector_store_provider.lower() == "milvus":
        # Milvus 后端仅评测时也需先建立连接/加载 collection
        from app.core.milvus_client import init_milvus

        asyncio.run(init_milvus(recreate=False))

    # 构造 retriever(按 --rerank 选精排策略)
    if args.rerank == "passthrough":
        from app.rag.reranker import PassthroughReranker

        reranker = PassthroughReranker()
        logger.info("评测模式: PassthroughReranker(粗排顺序即最终顺序)")
    elif args.rerank == "llm":
        from app.rag.reranker import LLMReranker

        reranker = LLMReranker()  # 用 get_lite_llm()(本地 ollama)
        logger.info("评测模式: LLMReranker(本地 ollama,每条样本会调多次 LLM,较慢)")
    elif args.rerank == "local_bge":
        from app.rag.reranker import BgeLocalReranker

        reranker = BgeLocalReranker()
        logger.info("评测模式: BgeLocalReranker(本地 bge-reranker-large)")
    else:
        # auto: 走 get_reranker() 工厂(按 .env RERANKER_PROVIDER)
        reranker = None
        logger.info("评测模式: auto(按 .env RERANKER_PROVIDER)")

    retriever = EnterpriseRAGRetriever(
        top_k=args.top_k, rerank_top_n=args.rerank_n, reranker=reranker
    )

    # 评测(检索层同步逐条;答案层集中在同一事件循环内执行——
    # LLM 单例的异步客户端绑定首个事件循环,逐条 asyncio.run 会因
    # loop 关闭导致 "Event loop is closed")
    print(f"\n开始评测(top_k={args.top_k}, rerank_n={args.rerank_n}, answer={args.with_answer})...")
    results: list[SampleResult] = []
    for i, sample in enumerate(samples, start=1):
        sr = evaluate_single(retriever, sample)
        results.append(sr)
        status = "✓" if sr.hit_at_5 else "✗"
        print(
            f"  [{i:2d}/{len(samples)}] {status} {sr.query_id} "
            f"Top5={'Y' if sr.hit_at_5 else 'N'} "
            f"score={sr.top_score:.3f} {sr.latency_ms}ms"
        )

    if args.with_answer:
        asyncio.run(_run_answer_phase(results))
        for sr in results:
            if sr.answer_status == "ok":
                if sr.expected_behavior == "answer":
                    print(f"  {sr.query_id} 答案覆盖={sr.answer_keyword_coverage:.2f}")
                else:
                    print(f"  {sr.query_id} 行为命中={'Y' if sr.behavior_detected else 'N'}")
            elif sr.answer_status == "failed":
                print(f"  {sr.query_id} 生成失败")

    # 汇总
    report = aggregate_report(results)
    print_report(report, target_top5=args.target, target_answer=args.answer_target)

    # 保存报告
    output_path = (
        Path(args.output) if args.output else Path(__file__).parent / "results" / "latest.json"
    )
    save_report_json(report, output_path)

    # 退出码(便于 CI 集成):检索层必过;启用答案层时按规格以答案覆盖率为达标判定
    passed = report.top5_hit_rate >= args.target
    if args.with_answer:
        passed = passed and (
            report.answer_evaluated > 0 and report.avg_answer_keyword_coverage >= args.answer_target
        )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
