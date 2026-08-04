"""Milvus 文档入库服务(对应 v3 方案 6.2 节)

W3 重构:依赖 VectorStore 抽象(支持 Milvus / InMemory 双后端)。
- 生产:VECTOR_STORE_PROVIDER=milvus
- 开发:VECTOR_STORE_PROVIDER=memory(无需 Docker)

入库流程:
1. 加载文件(md/txt/pdf/docx)
2. RecursiveCharacterTextSplitter 切分
3. EmbeddingService 向量化
4. VectorStore.add_documents(带 dept_namespace / access_roles / doc_type)
"""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import text

from app.rag.document_loader import DocumentLoader
from app.rag.embeddings import get_embeddings
from app.rag.vector_store import ChunkData, EnterpriseVectorStore, get_vector_store


class MilvusIngestService:
    """文档入库服务(命名保留历史兼容,实际后端由配置决定)"""

    def __init__(self, vector_store: Optional[EnterpriseVectorStore] = None):
        self.vector_store = vector_store or get_vector_store()
        self.embeddings = get_embeddings()
        self.loader = DocumentLoader(chunk_size=500, chunk_overlap=50)

    async def ingest_file(
        self,
        file_path: str | Path,
        document_id: Optional[str] = None,
        title: Optional[str] = None,
        doc_type: str = "policy",
        dept_namespace: str = "shared_company",
        access_roles: Optional[list[str]] = None,
        source_url: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> int:
        """入库单个文件,返回入库 chunk 数"""
        path = Path(file_path)
        document_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        title = title or path.stem
        access_roles = access_roles or [
            "salesperson", "customer_service", "finance", "manager", "admin"
        ]

        logger.info(f"开始入库: {path.name} → document_id={document_id}")

        # 1. 加载并切分
        docs = self.loader.load_file(path)
        chunks = self.loader.split_documents(docs)

        if not chunks:
            logger.warning(f"文件 {path.name} 切分后无 chunks,跳过")
            return 0

        # 2. 向量化
        texts = [chunk.page_content for chunk in chunks]
        embeddings = self.embeddings.embed_documents(texts)
        logger.info(f"生成 {len(embeddings)} 个向量, dim={len(embeddings[0])}")

        # 3. 构造 ChunkData 列表
        now_ts = int(datetime.now().timestamp())
        chunk_data_list = [
            ChunkData(
                chunk_id=f"{document_id}_chunk_{i:04d}",
                document_id=document_id,
                title=title[:512],
                content=chunk.page_content[:8192],
                embedding=embeddings[i],
                dept_namespace=dept_namespace,
                doc_type=doc_type,
                source_url=(source_url or "")[:1024],
                updated_at=now_ts,
                access_roles=access_roles,
                is_active=True,
            )
            for i, chunk in enumerate(chunks)
        ]

        # 4. 写入 VectorStore
        count = self.vector_store.add_documents(chunk_data_list, partition=dept_namespace)

        # 5. 同步写入 PostgreSQL documents 台账(知识库运营闭环的事实源)
        #    向量写入成功 → status=active;失败 → status=failed + ingest_error(可重试)
        ledger = {
            "document_id": document_id,
            "title": title[:512],
            "source_url": (source_url or "")[:1024],
            "doc_type": doc_type,
            "dept_namespace": dept_namespace,
            "status": "active",
            "access_roles": json.dumps(access_roles, ensure_ascii=False),
            "content_hash": self._compute_content_hash([c.page_content for c in chunks]),
            "content": "\n\n".join(c.page_content for c in chunks)[:200000],
            "uploaded_by": uploaded_by,
            "ingest_error": None,
        }
        try:
            await self._upsert_ledger(ledger)
            logger.info(
                f"入库完成: {path.name} → {count} chunks, "
                f"partition={dept_namespace}, document_id={document_id}"
            )
        except Exception as e:  # noqa: BLE001 台账失败不阻断向量结果,但要留下可观测错误
            logger.error(f"文档台账写入失败(document_id={document_id}): {e}")
            await self._mark_ledger_failed(document_id, str(e))

        return count

    async def ingest_text(
        self,
        document_id: str,
        title: str,
        content: str,
        doc_type: str = "faq",
        dept_namespace: str = "shared_company",
        access_roles: Optional[list[str]] = None,
        uploaded_by: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> int:
        """将纯文本内容直接向量化入库(知识候选审核通过时使用)

        Args:
            document_id: 文档唯一 ID
            title: 文档标题
            content: 文档正文(候选的评论/知识点内容)
            doc_type: 文档类型,默认 faq
            dept_namespace: 部门命名空间
            access_roles: 可访问角色列表
            uploaded_by: 上传者 user_id
            source_url: 来源链接(可选)

        Returns:
            入库 chunk 数;切分为空或向量化失败时抛异常由调用方处理
        """
        from langchain_core.documents import Document

        access_roles = access_roles or [
            "salesperson", "customer_service", "finance", "manager", "admin"
        ]
        chunks = self.loader.split_documents([Document(page_content=content)])
        if not chunks:
            logger.warning(f"知识候选内容切分后无 chunks: {document_id}")
            return 0

        texts = [chunk.page_content for chunk in chunks]
        embeddings = self.embeddings.embed_documents(texts)

        now_ts = int(datetime.now().timestamp())
        chunk_data_list = [
            ChunkData(
                chunk_id=f"{document_id}_chunk_{i:04d}",
                document_id=document_id,
                title=title[:512],
                content=chunk.page_content[:8192],
                embedding=embeddings[i],
                dept_namespace=dept_namespace,
                doc_type=doc_type,
                source_url=(source_url or "")[:1024],
                updated_at=now_ts,
                access_roles=access_roles,
                is_active=True,
            )
            for i, chunk in enumerate(chunks)
        ]

        count = self.vector_store.add_documents(
            chunk_data_list, partition=dept_namespace
        )
        await self._upsert_ledger(
            {
                "document_id": document_id,
                "title": title[:512],
                "source_url": (source_url or "")[:1024],
                "doc_type": doc_type,
                "dept_namespace": dept_namespace,
                "status": "active",
                "access_roles": json.dumps(access_roles, ensure_ascii=False),
                "content_hash": self._compute_content_hash(texts),
                "content": "\n\n".join(texts)[:200000],
                "uploaded_by": uploaded_by,
                "ingest_error": None,
            }
        )
        logger.info(
            f"文本入库完成: {document_id} → {count} chunks, "
            f"partition={dept_namespace}"
        )
        return count

    async def ingest_directory(
        self,
        dir_path: str | Path,
        doc_type: str = "policy",
        dept_namespace: str = "shared_company",
        access_roles: Optional[list[str]] = None,
    ) -> dict:
        """入库整个目录,返回统计"""
        path = Path(dir_path)
        stats = {"total_files": 0, "success_files": 0, "failed_files": 0, "total_chunks": 0}

        for ext in ["*.md", "*.txt", "*.pdf", "*.docx"]:
            for file in path.rglob(ext):
                stats["total_files"] += 1
                try:
                    chunks = await self.ingest_file(
                        file_path=file,
                        doc_type=doc_type,
                        dept_namespace=dept_namespace,
                        access_roles=access_roles,
                    )
                    stats["success_files"] += 1
                    stats["total_chunks"] += chunks
                except Exception as e:
                    logger.error(f"入库失败 {file}: {e}")
                    stats["failed_files"] += 1

        logger.info(f"目录入库完成: {stats}")
        return stats

    def delete_document(self, document_id: str) -> int:
        """删除文档(所有 chunks)"""
        return self.vector_store.delete_document(document_id)

    def get_stats(self) -> dict:
        """获取知识库统计"""
        return self.vector_store.get_stats()

    # ============ 台账辅助(内部) ============

    @staticmethod
    def _compute_content_hash(chunk_texts: list[str]) -> str:
        """按全部 chunk 正文计算内容哈希,用于重复导入去重"""
        digest = hashlib.sha256()
        for chunk_text in chunk_texts:
            digest.update(chunk_text.encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    async def _upsert_ledger(ledger: dict) -> None:
        """幂等 upsert documents 台账(同一 document_id 重复入库更新为最新内容)"""
        from app.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text(
                    "INSERT INTO documents (document_id, title, source_url, doc_type, "
                    "dept_namespace, status, access_roles, content_hash, content, "
                    "uploaded_by, ingest_error) "
                    "VALUES (:document_id, :title, :source_url, :doc_type, "
                    ":dept_namespace, :status, CAST(:access_roles AS JSONB), "
                    ":content_hash, :content, :uploaded_by, :ingest_error) "
                    "ON CONFLICT (document_id) DO UPDATE SET "
                    "title = EXCLUDED.title, source_url = EXCLUDED.source_url, "
                    "doc_type = EXCLUDED.doc_type, dept_namespace = EXCLUDED.dept_namespace, "
                    "status = EXCLUDED.status, access_roles = EXCLUDED.access_roles, "
                    "content_hash = EXCLUDED.content_hash, content = EXCLUDED.content, "
                    "uploaded_by = EXCLUDED.uploaded_by, ingest_error = EXCLUDED.ingest_error, "
                    "updated_at = CURRENT_TIMESTAMP"
                ),
                ledger,
            )
            await session.commit()

    @staticmethod
    async def _mark_ledger_failed(document_id: str, error_message: str) -> None:
        """向量写入或台账写入失败时,在台账保留失败标记供 worker 重试"""
        from app.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE documents SET status = 'failed', ingest_error = :error, "
                    "updated_at = CURRENT_TIMESTAMP WHERE document_id = :did"
                ),
                {"error": error_message[:500], "did": document_id},
            )
            await session.commit()


# ============ CLI 入口 ============


def main():
    """命令行入口:python -m app.rag.ingest <file_or_dir> [--type policy] [--ns shared_company] [--recreate]"""
    import argparse

    parser = argparse.ArgumentParser(description="企业知识库入库工具")
    parser.add_argument("path", help="文件或目录路径")
    parser.add_argument("--type", default="policy", help="文档类型: policy/product/faq/manual")
    parser.add_argument("--ns", default="shared_company", help="部门命名空间")
    parser.add_argument("--roles", nargs="*", default=None, help="可访问角色列表")
    parser.add_argument("--title", default=None, help="文档标题(单文件时使用)")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="危险:删除并重建 Milvus Collection(仅 milvus 后端有效,会清空所有数据)",
    )
    args = parser.parse_args()

    # Milvus 后端需要先初始化;memory 后端不需要
    from app.config import get_settings

    settings = get_settings()
    if settings.vector_store_provider.lower() == "milvus":
        import asyncio
        from app.core.milvus_client import init_milvus

        asyncio.run(init_milvus(recreate=args.recreate))

    import asyncio

    from app.core.database import init_db

    async def run_cli() -> None:
        """CLI 异步入口(台账写入依赖 PG)"""
        await init_db()
        service = MilvusIngestService()
        path = Path(args.path)

        if path.is_file():
            count = await service.ingest_file(
                file_path=path,
                title=args.title,
                doc_type=args.type,
                dept_namespace=args.ns,
                access_roles=args.roles,
            )
            print(f"入库完成: {count} chunks")
        elif path.is_dir():
            stats = await service.ingest_directory(
                dir_path=path,
                doc_type=args.type,
                dept_namespace=args.ns,
                access_roles=args.roles,
            )
            print(f"目录入库完成: {stats}")
        else:
            print(f"路径不存在: {path}")

        print("\n知识库统计:")
        print(service.get_stats())

    asyncio.run(run_cli())


if __name__ == "__main__":
    main()
