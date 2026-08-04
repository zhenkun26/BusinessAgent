"""企业知识库 RAG Retriever(对应 v3 方案 6.4 节)

两阶段检索:
1. 粗排:VectorStore 向量召回 Top-K(默认 K=top_k * 4,扩大候选池)
2. 精排:Reranker(Cohere / LLM)重排,返回 Top-N

支持:
- RBAC 过滤(按 user_role 限定 access_roles)
- 命名空间隔离(dept_namespace)
- 文档类型白名单(doc_types)
- 自动场景识别(为 ConfidenceDecider 准备 scene 参数)
"""

import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.observability.tracing import (
    record_span_attributes,
    record_span_event,
    traced_span,
)
from app.rag.confidence import ConfidenceDecider
from app.rag.embeddings import get_embeddings
from app.rag.reranker import Reranker, get_reranker
from app.rag.vector_store import (
    EnterpriseVectorStore,
    SearchFilter,
    SearchResult,
    get_vector_store,
)


@dataclass
class RetrievalResult:
    """检索结果包"""

    results: list[SearchResult]
    top_score: float  # Top-1 分数
    scene: str  # 识别出的场景
    latency_ms: int
    stage: str  # "vector" | "rerank" | "bm25" | "like"  命中的检索阶段(降级链用)


# 政策场景共享优先的平局噪声带(见 retrieve 中的说明)
_SHARED_PRIORITY_EPS = 0.03
_SHARED_NAMESPACE = "shared_company"


def _shared_priority_tiebreak(ranked: list) -> list:
    """政策场景下,噪声带(ε)内的 shared_company 结果排在部门结果之前

    稳定重排:带内按 shared 优先、各自保持原分数顺序;带外结果不动。
    """
    if not ranked:
        return ranked
    top = ranked[0].score
    near = [r for r in ranked if r.score >= top - _SHARED_PRIORITY_EPS]
    far = [r for r in ranked if r.score < top - _SHARED_PRIORITY_EPS]
    shared = [r for r in near if r.dept_namespace == _SHARED_NAMESPACE]
    dept = [r for r in near if r.dept_namespace != _SHARED_NAMESPACE]
    if not shared or not dept:
        return ranked  # 带内单一来源,无需裁决
    return shared + dept + far


class EnterpriseRAGRetriever:
    """两阶段 RAG 检索器"""

    def __init__(
        self,
        vector_store: Optional[EnterpriseVectorStore] = None,
        reranker: Optional[Reranker] = None,
        embeddings=None,
        top_k: int = 10,
        rerank_top_n: int = 5,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.reranker = reranker or get_reranker()
        self.embeddings = embeddings or get_embeddings()
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n

    def retrieve(
        self,
        query: str,
        user_role: Optional[str] = None,
        dept_namespace: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
        scene: Optional[str] = None,
    ) -> RetrievalResult:
        """执行两阶段检索

        Args:
            query: 用户查询
            user_role: 用户角色(RBAC 过滤)
            dept_namespace: 部门命名空间
            doc_types: 文档类型白名单
            scene: 场景(None 时自动识别)
        """
        start = time.time()

        # tracing: 整个 retrieve 作为一个 span(含子 span:粗排/精排)
        with traced_span(
            "rag.retrieve",
            attributes={
                "rag.query": query[:200],
                "rag.user_role": user_role or "",
                "rag.dept_namespace": dept_namespace or "",
                "rag.top_k": self.top_k,
                "rag.rerank_top_n": self.rerank_top_n,
            },
        ):
            # 1. 场景识别
            if scene is None:
                scene = ConfidenceDecider.detect_scene(query)
            record_span_attributes({"rag.scene": scene})

            # 2. query 向量化
            with traced_span("rag.embed_query"):
                query_embedding = self.embeddings.embed_query(query)

            # 3. 构造过滤条件
            search_filter = SearchFilter(
                user_role=user_role,
                dept_namespace=dept_namespace,
                doc_types=doc_types,
                active_only=True,
            )

            # 4. 粗排:向量召回(扩大候选池)
            with traced_span("rag.coarse_search") as coarse_ctx:
                coarse_k = max(self.top_k * 4, self.rerank_top_n * 8)
                coarse_results = self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=coarse_k,
                    filter=search_filter,
                )
                record_span_attributes({
                    "rag.coarse.count": len(coarse_results),
                    "rag.coarse.k": coarse_k,
                })

            coarse_ms = int((time.time() - start) * 1000)
            top_score_str = f"{coarse_results[0].score:.3f}" if coarse_results else "N/A"
            logger.info(
                f"RAG 粗排: 召回 {len(coarse_results)} 条, top_score={top_score_str}, "
                f"cost={coarse_ms}ms"
            )

            if not coarse_results:
                record_span_event("rag.no_results", {"stage": "coarse"})
                return RetrievalResult(
                    results=[],
                    top_score=0.0,
                    scene=scene,
                    latency_ms=coarse_ms,
                    stage="vector",
                )

            # 5. 精排:Reranker
            try:
                with traced_span("rag.rerank") as rerank_ctx:
                    ranked = self.reranker.rerank(query, coarse_results, top_n=self.rerank_top_n)
                    stage = "rerank"
                    record_span_attributes({
                        "rag.rerank.count": len(ranked),
                        "rag.rerank.top_score": ranked[0].score if ranked else 0.0,
                    })
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Rerank 失败,降级使用粗排结果: {e}")
                ranked = coarse_results[: self.rerank_top_n]
                stage = "vector"
                record_span_event("rag.rerank_failed", {"error": str(e)})

            total_ms = int((time.time() - start) * 1000)

            # 政策场景共享优先平局裁决:
            # 问"政策/规定/流程"时,公司级 shared 文档是权威来源;dept 文档与
            # shared 分数差距在噪声带(ε)内时,shared 排前——避免部门内部方案
            # 以噪声级优势盖过公司政策(实测:提成政策查询 dept 0.528 vs
            # shared 0.511,差距 0.017 属排序噪声,但会把错误来源顶到 top1)。
            # 差距 > ε 时不干预:dept 文档明显更相关时仍能胜出。
            if scene == "policy":
                ranked = _shared_priority_tiebreak(ranked)

            top_score = ranked[0].score if ranked else 0.0

            logger.info(
                f"RAG 精排: 返回 {len(ranked)} 条, top_score={top_score:.3f}, "
                f"stage={stage}, total_cost={total_ms}ms"
            )

            record_span_attributes({
                "rag.final.stage": stage,
                "rag.final.top_score": top_score,
                "rag.latency_ms": total_ms,
            })

            return RetrievalResult(
                results=ranked,
                top_score=top_score,
                scene=scene,
                latency_ms=total_ms,
                stage=stage,
            )

    def retrieve_with_text(
        self,
        query: str,
        user_role: Optional[str] = None,
        dept_namespace: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
    ) -> tuple[list[SearchResult], str, float]:
        """便捷方法:返回 (results, scene, top_score)"""
        r = self.retrieve(
            query=query,
            user_role=user_role,
            dept_namespace=dept_namespace,
            doc_types=doc_types,
        )
        return r.results, r.scene, r.top_score
