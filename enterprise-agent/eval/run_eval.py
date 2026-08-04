"""RAG 评测脚本(对应 v3 方案 W4 验收)

用法:
    # 1. 自动入库 + 评测(memory 后端,无需 Docker)
    python -m eval.run_eval --ingest

    # 2. 仅评测(假设 VectorStore 已有数据)
    python -m eval.run_eval

    # 3. 重建 VectorStore 后评测(milvus 后端,会清空数据)
    python -m eval.run_eval --ingest --recreate

评测指标:
- Top-K 命中率(K=1/3/5):Top-K 中是否包含 ground_truth_doc 的 chunk
- MRR(Mean Reciprocal Rank):第一个命中 chunk 的排名倒数
- 关键词覆盖率:expected_keywords 在 Top-K content 中的出现比例
- 分场景命中率:policy / factual / inferential
- 分难度命中率:easy / medium / hard

验收标准:Top-5 命中率 ≥ 85%
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

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
    """单条样本评测结果"""

    query_id: str
    query: str
    ground_truth_doc: str
    ground_truth_section: str
    expected_keywords: list[str]
    scene: str
    difficulty: str
    # 检索结果
    top_k_chunks: list[dict] = field(default_factory=list)  # [{title, score, doc_match}]
    # 指标
    hit_at_1: bool = False
    hit_at_3: bool = False
    hit_at_5: bool = False
    first_hit_rank: int = 0  # 0 表示未命中
    reciprocal_rank: float = 0.0
    keyword_coverage: float = 0.0
    top_score: float = 0.0
    latency_ms: int = 0


@dataclass
class EvalReport:
    """评测总报告"""

    total: int
    top1_hit_rate: float
    top3_hit_rate: float
    top5_hit_rate: float
    mrr: float
    avg_keyword_coverage: float
    avg_latency_ms: float
    by_scene: dict[str, dict] = field(default_factory=dict)
    by_difficulty: dict[str, dict] = field(default_factory=dict)
    samples: list[SampleResult] = field(default_factory=list)


def load_eval_set() -> dict:
    if not EVAL_SET_PATH.exists():
        raise FileNotFoundError(f"评测集不存在: {EVAL_SET_PATH}")
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        return json.load(f)


def ensure_ingest(recreate: bool = False) -> dict:
    """自动入库 sample_docs(若 VectorStore 为空)"""
    settings = get_settings()

    # Milvus 后端需先 init
    if settings.vector_store_provider.lower() == "milvus":
        from app.core.milvus_client import init_milvus

        asyncio.run(init_milvus(recreate=recreate))
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
    stats = service.ingest_directory(
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
    ground_truth_doc = sample["ground_truth_doc"]
    for rank, chunk in enumerate(result.results, start=1):
        doc_match = chunk.title == ground_truth_doc or ground_truth_doc in chunk.title
        sr.top_k_chunks.append(
            {
                "rank": rank,
                "title": chunk.title,
                "score": chunk.score,
                "doc_match": doc_match,
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
    if sr.expected_keywords:
        top5_text = " ".join(
            c.content for c in result.results[:5]
        ).lower()
        hits = sum(1 for kw in sr.expected_keywords if kw.lower() in top5_text)
        sr.keyword_coverage = hits / len(sr.expected_keywords)

    return sr


def aggregate_report(results: list[SampleResult]) -> EvalReport:
    """汇总评测报告"""
    total = len(results)
    if total == 0:
        return EvalReport(total=0, top1_hit_rate=0, top3_hit_rate=0, top5_hit_rate=0,
                          mrr=0, avg_keyword_coverage=0, avg_latency_ms=0)

    top1 = sum(1 for r in results if r.hit_at_1) / total
    top3 = sum(1 for r in results if r.hit_at_3) / total
    top5 = sum(1 for r in results if r.hit_at_5) / total
    mrr = sum(r.reciprocal_rank for r in results) / total
    kw_cov = sum(r.keyword_coverage for r in results) / total
    avg_lat = sum(r.latency_ms for r in results) / total

    # 分场景
    by_scene: dict[str, dict] = {}
    for scene in ["factual", "policy", "inferential"]:
        subset = [r for r in results if r.scene == scene]
        if subset:
            by_scene[scene] = {
                "total": len(subset),
                "top5_hit_rate": sum(1 for r in subset if r.hit_at_5) / len(subset),
                "mrr": sum(r.reciprocal_rank for r in subset) / len(subset),
            }

    # 分难度
    by_diff: dict[str, dict] = {}
    for diff in ["easy", "medium", "hard"]:
        subset = [r for r in results if r.difficulty == diff]
        if subset:
            by_diff[diff] = {
                "total": len(subset),
                "top5_hit_rate": sum(1 for r in subset if r.hit_at_5) / len(subset),
                "mrr": sum(r.reciprocal_rank for r in subset) / len(subset),
            }

    return EvalReport(
        total=total,
        top1_hit_rate=top1,
        top3_hit_rate=top3,
        top5_hit_rate=top5,
        mrr=mrr,
        avg_keyword_coverage=kw_cov,
        avg_latency_ms=avg_lat,
        by_scene=by_scene,
        by_difficulty=by_diff,
        samples=results,
    )


def print_report(report: EvalReport, target_top5: float = 0.85) -> None:
    """打印评测报告"""
    print("\n" + "=" * 60)
    print("📊 RAG 评测报告")
    print("=" * 60)
    print(f"样本总数: {report.total}")
    print(f"Top-1 命中率: {report.top1_hit_rate:.2%}")
    print(f"Top-3 命中率: {report.top3_hit_rate:.2%}")
    print(f"Top-5 命中率: {report.top5_hit_rate:.2%}  (目标 ≥ {target_top5:.0%})")
    print(f"MRR:         {report.mrr:.4f}")
    print(f"关键词覆盖率: {report.avg_keyword_coverage:.2%}")
    print(f"平均延迟:    {report.avg_latency_ms:.0f} ms")

    print("\n--- 分场景 ---")
    for scene, s in report.by_scene.items():
        print(f"  {scene:12s}  n={s['total']:2d}  Top5={s['top5_hit_rate']:.2%}  MRR={s['mrr']:.4f}")

    print("\n--- 分难度 ---")
    for diff, s in report.by_difficulty.items():
        print(f"  {diff:8s}  n={s['total']:2d}  Top5={s['top5_hit_rate']:.2%}  MRR={s['mrr']:.4f}")

    # 验收
    print("\n" + "=" * 60)
    if report.top5_hit_rate >= target_top5:
        print(f"✅ 验收通过: Top-5 命中率 {report.top5_hit_rate:.2%} ≥ {target_top5:.0%}")
    else:
        gap = target_top5 - report.top5_hit_rate
        print(f"❌ 验收未通过: Top-5 命中率 {report.top5_hit_rate:.2%},差 {gap:.2%}")
        # 输出未命中样本
        missed = [s for s in report.samples if not s.hit_at_5]
        if missed:
            print(f"\n未命中样本({len(missed)} 条):")
            for s in missed[:10]:
                print(f"  [{s.query_id}] {s.query[:60]}")
                print(f"    ground_truth={s.ground_truth_doc} / {s.ground_truth_section}")
                if s.top_k_chunks:
                    print(f"    实际 Top-3: {[(c['title'], round(c['score'],3)) for c in s.top_k_chunks[:3]]}")
    print("=" * 60)


def save_report_json(report: EvalReport, output_path: Path) -> None:
    """保存 JSON 报告"""
    data = {
        "total": report.total,
        "top1_hit_rate": report.top1_hit_rate,
        "top3_hit_rate": report.top3_hit_rate,
        "top5_hit_rate": report.top5_hit_rate,
        "mrr": report.mrr,
        "avg_keyword_coverage": report.avg_keyword_coverage,
        "avg_latency_ms": report.avg_latency_ms,
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
        "--output", type=str, default=None, help="JSON 报告输出路径(默认 eval/results/latest.json)"
    )
    args = parser.parse_args()

    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    # 加载评测集
    eval_set = load_eval_set()
    samples = eval_set["samples"]
    print(f"加载评测集: {len(samples)} 条样本")

    # 入库(如需要)
    if args.ingest:
        ensure_ingest(recreate=args.recreate)

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

    # 评测
    print(f"\n开始评测(top_k={args.top_k}, rerank_n={args.rerank_n})...")
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

    # 汇总
    report = aggregate_report(results)
    print_report(report, target_top5=args.target)

    # 保存报告
    output_path = Path(args.output) if args.output else Path(__file__).parent / "results" / "latest.json"
    save_report_json(report, output_path)

    # 退出码(便于 CI 集成)
    sys.exit(0 if report.top5_hit_rate >= args.target else 1)


if __name__ == "__main__":
    main()
