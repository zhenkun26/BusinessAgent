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

import json
import re
import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.rag.vector_store import SearchResult
from app.rag.publication_visibility import publication_scope, visible_results
from app.security.retrieval_policy import (
    RetrievalAccessError, checked_string, milvus_literal, resolve_scope,
)


@dataclass
class DegradationResult:
    """降级链结果"""

    results: list[SearchResult]
    stage: str  # "vector" | "bm25" | "like" | "none"
    latency_ms: int
    error: Optional[str] = None


class KeywordRetriever:
    """关键词检索器(BM25 + PG LIKE 兜底)

    - 第一级:从 Milvus 全表扫描 + 关键词匹配(模拟 BM25)
    - 第二级:PostgreSQL tsvector 全文检索(documents.search_vector,第三级降链)

    简化实现:对 collection 做 query 关键词扫描,返回包含关键词的 chunks。
    适合 Milvus 不可用时的降级,不追求高准确率,只求"有结果"。
    """

    def __init__(self):
        from app.config import get_settings

        self._settings = get_settings()

    async def retrieve_by_keywords(
        self,
        query: str,
        top_k: int = 10,
        user_role: Optional[str] = None,
        dept_namespace: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """关键词检索(降级路径)"""
        resolve_scope(user_role, dept_namespace, doc_types)
        # 提取关键词(去停用词,保留 2 字以上中文/英文单词)
        keywords = self._extract_keywords(query)
        if not keywords:
            logger.warning(f"关键词提取为空,query={query!r}")
            return []

        # 第一级降级:Milvus 全表扫描 + Python 层关键词匹配
        try:
            results = visible_results(self._scan_via_milvus(
                keywords, top_k, user_role, dept_namespace, doc_types))
            if results:
                return results
            return await self._fallback_pg_tsvector(
                keywords, top_k, user_role, dept_namespace, doc_types)
        except RetrievalAccessError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"Milvus 关键词扫描失败: {e}")
            return await self._fallback_pg_tsvector(
                keywords, top_k, user_role, dept_namespace, doc_types
            )

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

    @staticmethod
    def _escape_milvus_expr_str(value: str) -> str:
        """Compatibility wrapper around the shared literal encoder."""
        return milvus_literal(value)

    def _scan_via_milvus(
        self,
        keywords: list[str],
        top_k: int,
        user_role: Optional[str],
        dept_namespace: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """通过 Milvus query() 全表扫描(性能差,仅降级用)

        生产环境应替换为 PostgreSQL tsvector 检索。
        """
        scope = resolve_scope(user_role, dept_namespace, doc_types)
        from app.core.milvus_client import get_collection

        collection = get_collection()
        collection.load()
        expr = scope.milvus_expression()

        # query() 拉取一批(限制 500,避免拉全表)
        results = collection.query(
            expr=expr,
            output_fields=[
                "chunk_id", "document_id", "title", "content",
                "dept_namespace", "doc_type", "source_url", "updated_at",
                "access_roles", "is_active",
            ],
            limit=500,
        )

        # Python 层关键词匹配 + 简单打分(命中数 / 总关键词数)
        scored: list[tuple[float, dict]] = []
        for entity in results:
            if not scope.allows(entity.get('dept_namespace'), entity.get('access_roles'),
                                entity.get('is_active'), entity.get('doc_type')):
                continue
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
                access_roles=list(e["access_roles"]),
                is_active=e["is_active"],
            )
            for s, e in scored
        ]

    async def _fallback_pg_tsvector(
        self,
        keywords: list[str],
        top_k: int,
        user_role: Optional[str],
        dept_namespace: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """PostgreSQL tsvector 全文检索(降级链第三级)

        Apply the same resolved namespace grant, role ACL and type constraints as
        vector retrieval. Invalid scope never becomes an unrestricted fallback.

        Args:
            keywords: 已提取的关键词列表
            top_k: 返回条数上限
            user_role: 当前用户角色(access_roles 过滤)
            dept_namespace: 当前用户部门(命名空间过滤)

        Returns:
            带 ts_rank 排序的检索结果;查询失败或库不可用时返回空列表
        """
        scope = resolve_scope(user_role, dept_namespace, doc_types)
        terms = [checked_string(term, 512) for term in keywords[:8]]
        if not terms or scope.doc_types == ():
            return []
        from sqlalchemy import text

        # Only generated parameter names enter SQL. Each term uses plain-text query parsing.
        query_sql = " || ".join(f"plainto_tsquery('simple', :term_{i})" for i in range(len(terms)))
        params: dict[str, object] = {f'term_{i}': term for i, term in enumerate(terms)}
        params.update({
            'kw': terms[0].replace('!', '!!').replace('%', '!%').replace('_', '!_'),
            'all_namespaces': scope.namespaces is None,
            'namespaces': json.dumps(scope.namespaces or []),
            'role': json.dumps([scope.role]),
            'all_types': scope.doc_types is None,
            'doc_types': json.dumps(scope.doc_types or []),
            'limit': top_k,
        })
        try:
            from app.core.database import get_session_factory

            async with get_session_factory()() as session:
                rows = (await session.execute(text(f"""
                    SELECT chunk_id, document_id, title, content, dept_namespace,
                           doc_type, source_url, updated_at, access_roles, status,
                           ts_rank_cd(COALESCE(search_vector,
                                      to_tsvector('simple', COALESCE(content, ''))),
                                      ({query_sql})) AS rank
                    FROM (
                        SELECT c.chunk_id, d.document_id, d.title, c.content, d.dept_namespace,
                            d.doc_type, d.source_url, d.updated_at, d.access_roles, d.status,
                            to_tsvector('simple', c.content) AS search_vector
                        FROM documents d JOIN knowledge_publications p
                          ON p.publication_id = d.active_publication AND p.document_id = d.document_id
                        CROSS JOIN LATERAL jsonb_to_recordset(p.chunks)
                          AS c(chunk_id TEXT, content TEXT)
                        WHERE p.state = 'published' AND d.pending_publication IS NULL
                    ) documents
                    WHERE status = 'active'
                      AND (search_vector @@ ({query_sql})
                           OR content ILIKE '%' || :kw || '%' ESCAPE '!')
                      AND (:all_namespaces OR dept_namespace IN (
                          SELECT jsonb_array_elements_text(CAST(:namespaces AS JSONB))))
                      AND access_roles @> CAST(:role AS JSONB)
                      AND (:all_types OR doc_type IN (
                          SELECT jsonb_array_elements_text(CAST(:doc_types AS JSONB))))
                    ORDER BY rank DESC
                    LIMIT :limit
                """), params)).fetchall()
        except Exception:  # Database failure never removes filters or returns raw errors.
            logger.error('RETRIEVAL_DATABASE_UNAVAILABLE')
            return []

        results: list[SearchResult] = []
        for row in rows:
            if not scope.allows(getattr(row, 'dept_namespace', None),
                                getattr(row, 'access_roles', None),
                                getattr(row, 'status', None) == 'active',
                                getattr(row, 'doc_type', None)):
                continue
            results.append(
                SearchResult(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    title=row.title or "",
                    content=row.content or "",
                    score=float(row.rank) if row.rank is not None else 0.0,
                    dept_namespace=row.dept_namespace or "",
                    doc_type=row.doc_type or "",
                    source_url=row.source_url or "",
                    updated_at=int(row.updated_at.timestamp()) if row.updated_at else 0,
                    access_roles=list(row.access_roles),
                    is_active=True,
                )
            )
        return visible_results(results)


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

    async def run(
        self, query: str, user_role: Optional[str] = None,
        dept_namespace: Optional[str] = None, doc_types: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> DegradationResult:
        scope = resolve_scope(user_role, dept_namespace, doc_types)
        async with publication_scope(scope):
            return await self._run(query, user_role, dept_namespace, doc_types, top_k)

    async def _run(
        self,
        query: str,
        user_role: Optional[str] = None,
        dept_namespace: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> DegradationResult:
        """执行降级链"""
        scope = resolve_scope(user_role, dept_namespace, doc_types)
        start = time.time()

        # 1. 主路径:向量检索
        try:
            r = self.primary.retrieve(
                query=query,
                user_role=user_role,
                dept_namespace=dept_namespace,
                doc_types=doc_types,
            )
            authorized = visible_results([result for result in r.results if scope.allows_result(result)])
            if authorized:
                return DegradationResult(
                    results=authorized,
                    stage="vector",
                    latency_ms=r.latency_ms,
                )
            # 结果为空,不一定是故障,可能是知识库真没数据。继续尝试关键词检索
            logger.info("向量检索结果为空,尝试关键词降级")
        except RetrievalAccessError:
            raise
        except Exception as e:  # noqa: BLE001
            from app.rag.model_profile import uses_remote_profile
            from app.rag.remote_models import RemoteModelError

            if (uses_remote_profile(self.keyword_retriever._settings)
                    and isinstance(e, RemoteModelError)):
                raise
            logger.error(f"向量检索异常,降级到关键词: {e}")

        # 2. 降级 1:BM25 / 关键词
        try:
            results = await self.keyword_retriever.retrieve_by_keywords(
                query=query, top_k=top_k, user_role=user_role,
                dept_namespace=dept_namespace, doc_types=doc_types,
            )
            results = visible_results([result for result in results if scope.allows_result(result)])
            if results:
                ms = int((time.time() - start) * 1000)
                logger.info(f"BM25 降级命中: {len(results)} 条, cost={ms}ms")
                return DegradationResult(
                    results=results,
                    stage="bm25",
                    latency_ms=ms,
                )
        except RetrievalAccessError:
            raise
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
