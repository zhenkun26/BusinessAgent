"""企业知识库 VectorStore 抽象层

设计目标:
- 业务层(Retriever/Ingest)只依赖 EnterpriseVectorStore 抽象接口
- 后端可切换:milvus(生产)/ memory(开发期 Mock,无需 Docker)
- 字段语义对应 v3 方案 6.1 节:dept_namespace / access_roles / doc_type / is_active

切换后端只需改 .env:VECTOR_STORE_PROVIDER=memory | milvus
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol

import numpy as np
from loguru import logger

from app.config import get_settings


# ============ 数据契约 ============


@dataclass
class ChunkData:
    """入库 chunk 标准结构"""

    chunk_id: str
    document_id: str
    title: str
    content: str
    embedding: list[float]
    dept_namespace: str = "shared_company"
    doc_type: str = "policy"
    source_url: str = ""
    updated_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    access_roles: list[str] = field(
        default_factory=lambda: ["salesperson", "customer_service", "finance", "manager", "admin"]
    )
    is_active: bool = True


@dataclass
class SearchResult:
    """检索结果"""

    chunk_id: str
    document_id: str
    title: str
    content: str
    score: float  # 0-1,越大越相关
    dept_namespace: str
    doc_type: str
    source_url: str
    updated_at: int


@dataclass
class SearchFilter:
    """检索过滤条件(RBAC + 命名空间)"""

    user_role: Optional[str] = None  # 用户角色,必须命中 access_roles
    dept_namespace: Optional[str] = None  # 部门命名空间,None 表示不限
    doc_types: Optional[list[str]] = None  # 文档类型白名单
    active_only: bool = True  # 只查 is_active=True


class EnterpriseVectorStore(Protocol):
    """企业知识库 VectorStore 抽象接口"""

    def add_documents(self, chunks: list[ChunkData], partition: str = "shared_company") -> int:
        """入库一批 chunks,返回入库条数"""
        ...

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter: Optional[SearchFilter] = None,
    ) -> list[SearchResult]:
        """向量检索 Top-K,返回按 score 降序的结果"""
        ...

    def delete_document(self, document_id: str) -> int:
        """删除文档(所有 chunks)"""
        ...

    def get_stats(self) -> dict:
        """获取统计信息"""
        ...


# ============ InMemory 实现(开发期 Mock) ============


class InMemoryVectorStore:
    """内存 VectorStore(开发期 Mock,无需 Docker)

    用 numpy 做余弦相似度,支持 access_roles / namespace 过滤。
    适合 W3-W4 单元测试与小规模验证,不可用于生产(进程重启数据丢失)。
    """

    def __init__(self, dim: int = 1024):
        self._dim = dim
        self._chunks: list[ChunkData] = []
        self._embeddings: Optional[np.ndarray] = None  # [N, dim]
        self._lock = asyncio.Lock()

    def add_documents(self, chunks: list[ChunkData], partition: str = "shared_company") -> int:
        if not chunks:
            return 0
        # 校验 dim
        for c in chunks:
            if len(c.embedding) != self._dim:
                raise ValueError(
                    f"chunk {c.chunk_id} embedding dim={len(c.embedding)} 不等于 store dim={self._dim}"
                )
        self._chunks.extend(chunks)
        # 重建 embeddings 矩阵(简单实现,数据量小够用)
        new_emb = np.array([c.embedding for c in self._chunks], dtype=np.float32)
        # L2 归一化(便于余弦相似度 = 内积)
        norms = np.linalg.norm(new_emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._embeddings = new_emb / norms
        logger.info(f"InMemoryVS 入库 {len(chunks)} chunks, 总数={len(self._chunks)}")
        return len(chunks)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter: Optional[SearchFilter] = None,
    ) -> list[SearchResult]:
        if not self._chunks or self._embeddings is None:
            return []

        # 归一化 query
        q = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        # 余弦相似度
        scores = self._embeddings @ q  # [N]

        # 过滤
        results: list[tuple[float, ChunkData]] = []
        for idx, chunk in enumerate(self._chunks):
            if filter and not self._match_filter(chunk, filter):
                continue
            results.append((float(scores[idx]), chunk))

        # 排序 + 截断
        results.sort(key=lambda x: x[0], reverse=True)
        results = results[:top_k]

        return [
            SearchResult(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                title=c.title,
                content=c.content,
                score=max(0.0, min(1.0, s)),  # clip 到 [0,1]
                dept_namespace=c.dept_namespace,
                doc_type=c.doc_type,
                source_url=c.source_url,
                updated_at=c.updated_at,
            )
            for s, c in results
        ]

    def delete_document(self, document_id: str) -> int:
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.document_id != document_id]
        # 重建 embeddings
        if self._chunks:
            new_emb = np.array([c.embedding for c in self._chunks], dtype=np.float32)
            norms = np.linalg.norm(new_emb, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._embeddings = new_emb / norms
        else:
            self._embeddings = None
        deleted = before - len(self._chunks)
        logger.info(f"InMemoryVS 删除 document_id={document_id}, 删除 {deleted} chunks")
        return deleted

    def get_stats(self) -> dict:
        return {
            "provider": "memory",
            "total_entities": len(self._chunks),
            "dim": self._dim,
            "partitions": list({c.dept_namespace for c in self._chunks}),
        }

    @staticmethod
    def _match_filter(chunk: ChunkData, f: SearchFilter) -> bool:
        if f.active_only and not chunk.is_active:
            return False
        if f.user_role and f.user_role not in chunk.access_roles:
            return False
        # 命名空间过滤:用户能看本部门 + 公司共享文档(对应 v3 方案 7.2 节)
        # - chunk.ns == shared_company:任何用户都可看
        # - chunk.ns == f.dept_namespace:本部门文档
        # - f.dept_namespace is None:不做命名空间过滤
        if f.dept_namespace and chunk.dept_namespace not in (
            f.dept_namespace,
            "shared_company",
        ):
            return False
        if f.doc_types and chunk.doc_type not in f.doc_types:
            return False
        return True


# ============ Milvus 实现(生产用) ============


class MilvusVectorStore:
    """Milvus VectorStore 实现

    包装 pymilvus.Collection,字段语义与 InMemoryVectorStore 一致。
    启动前需先调用 app.core.milvus_client.init_milvus()。
    """

    def __init__(self):
        from app.core.milvus_client import get_collection

        self.collection = get_collection()
        self._settings = get_settings()

    def add_documents(self, chunks: list[ChunkData], partition: str = "shared_company") -> int:
        if not chunks:
            return 0
        data = [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "title": c.title[:512],
                "content": c.content[:8192],
                "embedding": c.embedding,
                "dept_namespace": c.dept_namespace,
                "doc_type": c.doc_type,
                "source_url": (c.source_url or "")[:1024],
                "updated_at": c.updated_at,
                "access_roles": c.access_roles,
                "is_active": c.is_active,
            }
            for c in chunks
        ]
        partition_name = (
            partition if self.collection.has_partition(partition) else "shared_company"
        )
        if partition_name != partition:
            logger.warning(
                f"partition '{partition}' 不存在,数据落入 shared_company,"
                "部门文档可能被误共享"
            )
        self.collection.insert(data=data, partition_name=partition_name)
        self.collection.flush()
        logger.info(
            f"MilvusVS 入库 {len(data)} chunks, partition={partition_name}"
        )
        return len(data)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter: Optional[SearchFilter] = None,
    ) -> list[SearchResult]:
        # 构造 Milvus 过滤表达式
        expr_parts: list[str] = []
        if filter:
            if filter.active_only:
                expr_parts.append("is_active == true")
            if filter.user_role:
                # ARRAY 任一元素匹配:Milvus 用 ARRAY_CONTAINS
                expr_parts.append(f'ARRAY_CONTAINS(access_roles, "{filter.user_role}")')
            if filter.dept_namespace:
                # 命名空间过滤:本部门 + 公司共享(对应 v3 方案 7.2 节)
                expr_parts.append(
                    f'dept_namespace in ["{filter.dept_namespace}", "shared_company"]'
                )
            if filter.doc_types:
                types = ",".join([f'"{t}"' for t in filter.doc_types])
                expr_parts.append(f"doc_type in [{types}]")
        expr = " and ".join(expr_parts) if expr_parts else None

        # 检索字段
        output_fields = [
            "chunk_id", "document_id", "title", "content",
            "dept_namespace", "doc_type", "source_url", "updated_at",
        ]
        search_params = {"metric_type": "COSINE", "params": {"ef": max(top_k * 4, 64)}}

        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=output_fields,
        )

        hits = results[0] if results else []
        out: list[SearchResult] = []
        for hit in hits:
            entity = hit.entity.to_dict() if hasattr(hit.entity, "to_dict") else {}
            # pymilvus 2.4+ 返回 dict-like
            fields = entity.get("fields", entity) if isinstance(entity, dict) else entity
            out.append(
                SearchResult(
                    chunk_id=fields.get("chunk_id", ""),
                    document_id=fields.get("document_id", ""),
                    title=fields.get("title", ""),
                    content=fields.get("content", ""),
                    score=float(hit.score),
                    dept_namespace=fields.get("dept_namespace", ""),
                    doc_type=fields.get("doc_type", ""),
                    source_url=fields.get("source_url", ""),
                    updated_at=int(fields.get("updated_at", 0)),
                )
            )
        return out

    def delete_document(self, document_id: str) -> int:
        self.collection.delete(f'document_id == "{document_id}"')
        self.collection.flush()
        logger.info(f"MilvusVS 删除 document_id={document_id}")
        return 1

    def get_stats(self) -> dict:
        self.collection.flush()
        # pymilvus 2.4+ Partition 对象属性名为 .name(旧版 .partition_name 已废弃)
        partitions = []
        for p in self.collection.partitions:
            p_name = getattr(p, "name", None) or getattr(p, "partition_name", "unknown")
            partitions.append(p_name)
        return {
            "provider": "milvus",
            "collection": self.collection.name,
            "total_entities": self.collection.num_entities,
            "partitions": partitions,
        }


# ============ 工厂 ============


_vs_instance: Optional[EnterpriseVectorStore] = None


def get_vector_store() -> EnterpriseVectorStore:
    """获取 VectorStore 单例(根据配置选 milvus / memory)"""
    global _vs_instance
    if _vs_instance is not None:
        return _vs_instance

    settings = get_settings()
    provider = settings.vector_store_provider.lower()

    if provider == "milvus":
        _vs_instance = MilvusVectorStore()
        logger.info(f"VectorStore 后端: milvus, collection={settings.milvus_collection}")
    elif provider == "memory":
        _vs_instance = InMemoryVectorStore(dim=settings.embedding_dim)
        logger.info(f"VectorStore 后端: memory(InMemory Mock), dim={settings.embedding_dim}")
    else:
        raise ValueError(f"未知 vector_store_provider: {provider}")

    return _vs_instance


def reset_vector_store() -> None:
    """重置单例(测试用)"""
    global _vs_instance
    _vs_instance = None
