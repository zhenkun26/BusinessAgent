"""Milvus 文档入库服务(对应 v3 方案 6.2 节)

W3 重构:依赖 VectorStore 抽象(支持 Milvus / InMemory 双后端)。
- 生产:VECTOR_STORE_PROVIDER=milvus
- 开发:VECTOR_STORE_PROVIDER=memory(无需 Docker)

入库流程:
1. 加载文件(md/txt/pdf/docx)
2. RecursiveCharacterTextSplitter 切分
3. Persist an immutable generation before embedding or index I/O.
4. Embed and upsert its chunks, then atomically activate the ledger.
"""

import asyncio
import hashlib
from pathlib import Path
from typing import Optional

from loguru import logger

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
        """Trusted CLI import. Stage a version before indexing; propagate any failure."""
        path = Path(file_path)
        docs = self.loader.load_file(path)
        content = "\n\n".join(doc.page_content for doc in docs)
        return await self.ingest_text(
            document_id=document_id or "doc_" + hashlib.sha256(
                str(path.resolve()).encode()).hexdigest()[:48],
            title=title or path.stem, content=content, doc_type=doc_type,
            dept_namespace=dept_namespace, access_roles=access_roles,
            uploaded_by=uploaded_by, source_url=source_url,
        )

    async def ingest_text(
        self, document_id: str, title: str, content: str, doc_type: str = "faq",
        dept_namespace: str = "shared_company", access_roles: Optional[list[str]] = None,
        uploaded_by: Optional[str] = None, source_url: Optional[str] = None,
        publication_approval: Optional[dict] = None,
    ) -> int:
        """Persist a frozen generation, upsert exact IDs, then conditionally activate it."""
        from langchain_core.documents import Document
        from app.config import get_settings
        from app.core.knowledge_publication import PublicationStore
        from app.core.task_queue import TaskRejected

        # Missing/empty ACL is never expanded to all roles.
        data = dict(document_id=document_id, title=title, content=content,
                    doc_type=doc_type, dept_namespace=dept_namespace,
                    access_roles=access_roles, uploaded_by=uploaded_by,
                    source_url=source_url or "")
        texts = [c.page_content for c in self.loader.split_documents([Document(page_content=content)])]
        settings = get_settings()
        recipe = dict(provider=settings.embedding_provider, model=settings.embedding_model,
                      dim=settings.embedding_dim, splitter="recursive-500-50-v1")
        store = PublicationStore()
        try:
            record = await store.prepare(data, texts, recipe, publication_approval)
        except TaskRejected:
            raise
        except Exception:
            raise TaskRejected("KNOWLEDGE_STORE_UNAVAILABLE") from None
        if record['state'] == 'published':
            return len(record['chunks'])
        try:
            # Frozen content and IDs survive retries; never truncate after hashing.
            embeddings = self.embeddings.embed_documents([c['content'] for c in record['chunks']])
            if len(embeddings) != len(record['chunks']):
                raise TaskRejected('KNOWLEDGE_EMBEDDING_INCOMPLETE')
            chunks = [ChunkData(**chunk, embedding=vector)
                      for chunk, vector in zip(record['chunks'], embeddings, strict=True)]
            count = self.vector_store.add_documents(chunks, partition=dept_namespace)
            if type(count) is not int or count != len(chunks):
                raise TaskRejected('KNOWLEDGE_INDEX_INCOMPLETE')
            await store.activate(record)
            return count
        except BaseException as exc:
            try:
                await store.failed(record)
            except Exception:
                logger.warning('KNOWLEDGE_FAILURE_RECORD_UNAVAILABLE')
            if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                raise
            raise TaskRejected('KNOWLEDGE_PUBLICATION_UNCONFIRMED') from None

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
                except Exception:
                    logger.error("KNOWLEDGE_IMPORT_FAILED")
                    stats["failed_files"] += 1

        logger.info(f"目录入库完成: {stats}")
        return stats

    def delete_document(self, document_id: str) -> int:
        """删除文档(所有 chunks)"""
        return self.vector_store.delete_document(document_id)

    def get_stats(self) -> dict:
        """获取知识库统计"""
        return self.vector_store.get_stats()

# ============ CLI 入口 ============


def main():
    """命令行入口:python -m app.rag.ingest <file_or_dir> [--type policy] [--ns shared_company] [--recreate]"""
    import argparse

    parser = argparse.ArgumentParser(description="企业知识库入库工具")
    parser.add_argument("path", help="文件或目录路径")
    parser.add_argument("--type", default="policy", help="文档类型: policy/product/faq/manual")
    parser.add_argument("--ns", default="shared_company", help="部门命名空间")
    parser.add_argument("--roles", nargs="*", required=True, help="Explicit access roles (required)")
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
