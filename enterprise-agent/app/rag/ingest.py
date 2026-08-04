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

import uuid
from datetime import datetime
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

    def ingest_file(
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

        logger.info(
            f"入库完成: {path.name} → {count} chunks, "
            f"partition={dept_namespace}, document_id={document_id}"
        )

        # 5. 同步写入 PostgreSQL documents 表(可选,知识库运营后台用)
        # TODO W12: 接入 documents 表写入

        return count

    def ingest_directory(
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
                    chunks = self.ingest_file(
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

    service = MilvusIngestService()
    path = Path(args.path)

    if path.is_file():
        count = service.ingest_file(
            file_path=path,
            title=args.title,
            doc_type=args.type,
            dept_namespace=args.ns,
            access_roles=args.roles,
        )
        print(f"入库完成: {count} chunks")
    elif path.is_dir():
        stats = service.ingest_directory(
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


if __name__ == "__main__":
    main()
