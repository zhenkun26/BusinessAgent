"""Milvus 三级降级链(对应 v3 方案 P0-3)

降级顺序:
1. 向量检索(主):Milvus HNSW
2. BM25 检索(降级 1):Milvus 2.4+ 内置 BM25,或 PostgreSQL 全文检索
3. PostgreSQL LIKE(降级 2):兜底,关键词模糊匹配

触发条件:
- 主路径异常(Milvus 连接失败/超时)→ BM25
- BM25 异常或不可用 → PG LIKE
- 全部失败 → 返回空 + 告警

W3 实现要点:
- 向量检索走 EnterpriseRAGRetriever(已封装)
- BM25/PG LIKE 走 KeywordRetriever(本模块)
- DegradationChain 统一调度,记录命中的 stage
"""

import re
import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.rag.vector_store import SearchResult


@dataclass
class DegradationResult:
    """降级链结果"""

    results: list[SearchResult]
    stage: str  # "vector" | "bm25" | "like" | "none"
    latency_ms: int
    error: Optional[str] = None


class KeywordRetriever:
    """关键词检索器(BM25 + PG LIKE 兜底)

    W3 阶段:从 Milvus 全表扫描 + 关键词匹配(模拟 BM25)
    W11 阶段:接 PostgreSQL 全文索引(tsvector + ts_rank)

    简化实现:对 collection 做 query 关键词扫描,返回包含关键词的 chunks。
    适合 Milvus 不可用时的降级,不追求高准确率,只求"有结果"。
    """

    def __init__(self):
        from app.config import get_settings

        self._settings = get_settings()

    def retrieve_by_keywords(
        self,
        query: str,
        top_k: int = 10,
        user_role: Optional[str] = None,
        dept_namespace: Optional[str] = None,
    ) -> list[SearchResult]:
        """关键词检索(降级路径)"""
        # 提取关键词(去停用词,保留 2 字以上中文/英文单词)
        keywords = self._extract_keywords(query)
        if not keywords:
            logger.warning(f"关键词提取为空,query={query!r}")
            return []

        # W3 简化实现:从 Milvus 全表 query 所有 active chunks,匹配关键词
        # 生产实现应接 PostgreSQL documents 表的 tsvector 索引
        try:
            return self._scan_via_milvus(keywords, top_k, user_role, dept_namespace)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Milvus 关键词扫描失败: {e}")
            return self._fallback_pg_like(keywords, top_k, user_role, dept_namespace)

    @staticmethod
    def _extract_keywords(query: str) -> list[str]:
        """简单关键词提取(去标点、去单字、去停用词)"""
        stop_words = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都",
            "一", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
            "没有", "看", "好", "自己", "这", "那",
            "what", "how", "why", "when", "who", "the", "a", "an",
        }
        # 切词:中文按 2-3 字滑窗 + 英文按空格
        tokens: list[str] = []
        # 英文/数字
        en_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", query)
        tokens.extend([t.lower() for t in en_tokens if t.lower() not in stop_words])
        # 中文 2-4 字组合(简单滑窗)
        cn_chars = re.findall(r"[\u4e00-\u9fa5]+", query)
        for seg in cn_chars:
            for size in (4, 3, 2):
                if len(seg) >= size:
                    for i in range(len(seg) - size + 1):
                        w = seg[i : i + size]
                        if w not in stop_words:
                            tokens.append(w)
                            break  # 每个 seg 只取一个最长词,避免爆炸
        # 去重保序
        seen = set()
        out = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out[:8]  # 最多 8 个关键词

    def _scan_via_milvus(
        self,
        keywords: list[str],
        top_k: int,
        user_role: Optional[str],
        dept_namespace: Optional[str] = None,
    ) -> list[SearchResult]:
        """通过 Milvus query() 全表扫描(性能差,仅降级用)

        生产环境应替换为 PostgreSQL tsvector 检索。
        """
        from app.core.milvus_client import get_collection

        collection = get_collection()
        collection.load()

        # 构造过滤:任意关键词命中 content
        # Milvus 不支持 LIKE 多关键词 OR,只能逐个查或用 query() 全表
        # 简化:查所有 active chunks,在 Python 层做关键词匹配
        expr = "is_active == true"
        if user_role:
            expr += f' and ARRAY_CONTAINS(access_roles, "{user_role}")'
        if dept_namespace:
            # 命名空间隔离:本部门 + 公司共享(口径与 vector_store.search 一致)
            expr += f' and dept_namespace in ["{dept_namespace}", "shared_company"]'

        # query() 拉取一批(限制 500,避免拉全表)
        results = collection.query(
            expr=expr,
            output_fields=[
                "chunk_id", "document_id", "title", "content",
                "dept_namespace", "doc_type", "source_url", "updated_at",
            ],
            limit=500,
        )

        # Python 层关键词匹配 + 简单打分(命中数 / 总关键词数)
        scored: list[tuple[float, dict]] = []
        for entity in results:
            content = entity.get("content", "")
            title = entity.get("title", "")
            text = f"{title} {content}".lower()
            hits = sum(1 for kw in keywords if kw.lower() in text)
            if hits == 0:
                continue
            score = hits / len(keywords)
            scored.append((score, entity))

        scored.sort(key=lambda x: x[0], reverse=True)
        scored = scored[:top_k]

        return [
            SearchResult(
                chunk_id=e.get("chunk_id", ""),
                document_id=e.get("document_id", ""),
                title=e.get("title", ""),
                content=e.get("content", ""),
                score=s,
                dept_namespace=e.get("dept_namespace", ""),
                doc_type=e.get("doc_type", ""),
                source_url=e.get("source_url", ""),
                updated_at=int(e.get("updated_at", 0)),
            )
            for s, e in scored
        ]

    def _fallback_pg_like(
        self,
        keywords: list[str],
        top_k: int,
        user_role: Optional[str],
        dept_namespace: Optional[str] = None,
    ) -> list[SearchResult]:
        """PostgreSQL LIKE 兜底(需要 documents 表,W3 暂未实现)

        TODO W11:接 PostgreSQL documents 表时必须带 dept_namespace 过滤
        (本部门 + shared_company),避免降级路径泄露其他部门文档。
        """
        logger.warning("PG LIKE 兜底未实现,返回空结果")
        return []


class DegradationChain:
    """Milvus 三级降级链调度器

    使用方式:
        chain = DegradationChain(retriever)
        result = chain.run(query, user_role=...)
        # result.stage 告诉你命中了哪一级
    """

    def __init__(self, primary_retriever):
        """primary_retriever: EnterpriseRAGRetriever 实例"""
        self.primary = primary_retriever
        self.keyword_retriever = KeywordRetriever()

    def run(
        self,
        query: str,
        user_role: Optional[str] = None,
        dept_namespace: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> DegradationResult:
        """执行降级链"""
        start = time.time()

        # 1. 主路径:向量检索
        try:
            r = self.primary.retrieve(
                query=query,
                user_role=user_role,
                dept_namespace=dept_namespace,
                doc_types=doc_types,
            )
            if r.results:
                return DegradationResult(
                    results=r.results,
                    stage="vector",
                    latency_ms=r.latency_ms,
                )
            # 结果为空,不一定是故障,可能是知识库真没数据。继续尝试关键词检索
            logger.info("向量检索结果为空,尝试关键词降级")
        except Exception as e:  # noqa: BLE001
            logger.error(f"向量检索异常,降级到关键词: {e}")

        # 2. 降级 1:BM25 / 关键词
        try:
            results = self.keyword_retriever.retrieve_by_keywords(
                query=query, top_k=top_k, user_role=user_role,
                dept_namespace=dept_namespace,
            )
            if results:
                ms = int((time.time() - start) * 1000)
                logger.info(f"BM25 降级命中: {len(results)} 条, cost={ms}ms")
                return DegradationResult(
                    results=results,
                    stage="bm25",
                    latency_ms=ms,
                )
        except Exception as e:  # noqa: BLE001
            logger.error(f"BM25 降级异常: {e}")

        # 3. 全部失败
        ms = int((time.time() - start) * 1000)
        return DegradationResult(
            results=[],
            stage="none",
            latency_ms=ms,
            error="所有检索路径均失败",
        )
