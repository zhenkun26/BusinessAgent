"""Milvus 客户端与集合初始化"""

from typing import Optional

from loguru import logger
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config import get_settings

_collection: Optional[Collection] = None


def build_knowledge_schema(dim: int) -> CollectionSchema:
    """构建企业知识库 Collection Schema

    对应 v3 方案 6.1 节。dim 从配置读取,支持本地 bge-m3(1024)/OpenAI(1536)等不同 Embedding。
    """
    fields = [
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="dept_namespace", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="source_url", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="updated_at", dtype=DataType.INT64),
        FieldSchema(name="access_roles", dtype=DataType.ARRAY,
                    element_type=DataType.VARCHAR, max_length=32, max_capacity=20),
        FieldSchema(name="is_active", dtype=DataType.BOOL),
    ]
    return CollectionSchema(fields=fields, description="企业知识库向量索引")


INDEX_PARAMS = {
    "field_name": "embedding",
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}

# 部门 Partition 列表(对应 v3 方案 6.2 节)
PARTITIONS = [
    "dept_sales",
    "dept_finance",
    "dept_cs",
    "dept_hr",
    "shared_company",
    "restricted_exec",
]


async def init_milvus(recreate: bool = False):
    """初始化 Milvus 连接与 Collection

    Args:
        recreate: 开发期可传 True 强制 drop 重建(如 dim 变更后)
    """
    global _collection
    settings = get_settings()

    connections.connect(
        alias="default",
        uri=settings.milvus_uri,
        user=settings.milvus_user,
        password=settings.milvus_password,
    )

    collection_name = settings.milvus_collection

    # 开发期重建
    if recreate and utility.has_collection(collection_name):
        logger.warning(f"DROP 已存在的 Collection: {collection_name}")
        utility.drop_collection(collection_name)
        # 等待 drop 完成(Milvus 内部需要清理元数据)
        import time

        time.sleep(2)

    # 集合不存在则创建
    if not utility.has_collection(collection_name):
        logger.info(
            f"创建 Milvus Collection: {collection_name}, dim={settings.embedding_dim}"
        )
        schema = build_knowledge_schema(dim=settings.embedding_dim)
        _collection = Collection(
            name=collection_name,
            schema=schema,
            using="default",
            shards_num=2,
        )

        # 必须先 flush,使 schema 生效,再创建索引(pymilvus 2.4 要求)
        _collection.flush()

        # 创建 HNSW 索引(pymilvus 2.4+ 推荐用 index_params dict)
        try:
            from pymilvus import MilvusClient

            # 用新 API 创建索引(更可靠)
            client = MilvusClient(uri=settings.milvus_uri, user=settings.milvus_user, password=settings.milvus_password)
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name=INDEX_PARAMS["field_name"],
                index_type=INDEX_PARAMS["index_type"],
                metric_type=INDEX_PARAMS["metric_type"],
                params=INDEX_PARAMS["params"],
            )
            client.create_index(
                collection_name=collection_name,
                index_params=index_params,
            )
            logger.info(f"HNSW 索引已创建(新 API): {INDEX_PARAMS}")
        except Exception as e:
            logger.warning(f"新 API 创建索引失败,回退旧 API: {e}")
            _collection.create_index(
                field_name=INDEX_PARAMS["field_name"],
                index_type=INDEX_PARAMS["index_type"],
                metric_type=INDEX_PARAMS["metric_type"],
                params=INDEX_PARAMS["params"],
            )
            logger.info(f"HNSW 索引已创建(旧 API): {INDEX_PARAMS}")

        # 创建部门 Partition
        for partition_name in PARTITIONS:
            if not _collection.has_partition(partition_name):
                _collection.create_partition(partition_name)
        logger.info(f"Partition 已创建: {PARTITIONS}")

        # 再次 flush 确保 partition 生效
        _collection.flush()

    else:
        _collection = Collection(name=collection_name, using="default")
        logger.info(f"Milvus Collection 已存在: {collection_name}")

    # 加载到内存(必须先有索引才能 load)
    _collection.load()
    logger.info(f"Collection 已加载到内存, 行数: {_collection.num_entities}")


def get_collection() -> Collection:
    """获取 Milvus Collection(用于依赖注入)"""
    if _collection is None:
        raise RuntimeError("Milvus 未初始化,请先调用 init_milvus()")
    return _collection


async def check_milvus_health() -> dict:
    """健康检查"""
    try:
        if _collection is None:
            return {"status": "unhealthy", "reason": "未初始化"}
        return {
            "status": "healthy",
            "collection": _collection.name,
            "num_entities": _collection.num_entities,
        }
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}
