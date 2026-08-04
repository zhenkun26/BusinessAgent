"""W9-4 验证:Milvus 真实接入(memory → milvus 切换)

测试流程:
1. Milvus 连接 + Collection 初始化
2. 切换 VECTOR_STORE_PROVIDER=milvus
3. 入库 sample_docs 到 Milvus
4. 向量检索(带 RBAC + 命名空间过滤)
5. 三级降级链验证(向量 → BM25 → PG LIKE)
6. 端到端 RAG(KnowledgeAgent 完整流程)

前置:
- Milvus 容器已启动(docker compose up -d etcd minio milvus-standalone)
- bge-m3 模型可用(D:/models/bge-m3)
- DeepSeek API 可用(用于 RAG 答案生成)

运行:
    $env:VECTOR_STORE_PROVIDER="milvus"
    $env:MILVUS_HOST="localhost"
    python -m eval.run_w9_milvus
"""

import asyncio
import os
import uuid
from pathlib import Path

from loguru import logger

from app.security.rbac import AgentRole


# ============ 测试 1: Milvus 连接 + Collection 初始化 ============


async def test_milvus_init():
    """测试 1:Milvus 连接 + Collection 初始化"""
    print("\n" + "=" * 60)
    print("测试 1:Milvus 连接 + Collection 初始化")
    print("=" * 60)

    from app.core.milvus_client import init_milvus, check_milvus_health

    # 不强制重建(保留已入库数据);首次运行时 collection 不存在会自动创建
    await init_milvus(recreate=False)

    health = await check_milvus_health()
    print(f"健康状态: {health}")

    if health.get("status") != "healthy":
        print(f"✗ Milvus 健康检查失败: {health}")
        return False

    print(f"✓ Milvus 已就绪: collection={health.get('collection')}, entities={health.get('num_entities')}")
    return True


# ============ 测试 2: 入库 sample_docs ============


async def test_ingest_docs():
    """测试 2:入库样本文档到 Milvus"""
    print("\n" + "=" * 60)
    print("测试 2:入库样本文档到 Milvus")
    print("=" * 60)

    from app.rag.ingest import MilvusIngestService
    from app.rag.vector_store import get_vector_store, reset_vector_store

    # 重置单例(确保用新的 milvus 后端)
    reset_vector_store()

    vs = get_vector_store()
    stats = vs.get_stats()
    existing = stats.get("total_entities", 0) if isinstance(stats, dict) else 0

    if existing > 0:
        print(f"  Milvus 已有 {existing} entities,跳过入库(避免重复)")
        print(f"  VectorStore stats: {stats}")
        print(f"✓ 已有数据,跳过入库")
        return True

    sample_dir = Path(__file__).parent / "sample_docs"
    if not sample_dir.exists():
        print(f"✗ sample_docs 目录不存在: {sample_dir}")
        return False

    ingest = MilvusIngestService()
    total = 0
    for md_file in sorted(sample_dir.glob("*.md")):
        try:
            count = ingest.ingest_file(
                file_path=md_file,
                title=md_file.stem,
                doc_type="policy",
                dept_namespace="shared_company",
            )
            total += count
            print(f"  入库 {md_file.name}: {count} chunks")
        except Exception as e:
            print(f"  ✗ 入库 {md_file.name} 失败: {e}")
            return False

    # 验证 Collection 行数
    vs = get_vector_store()
    stats = vs.get_stats()
    print(f"  VectorStore stats: {stats}")

    if total == 0:
        print("✗ 入库 0 chunks")
        return False

    total_entities = stats.get("total_entities", 0)
    if total_entities < total:
        print(f"✗ 入库后 entities={total_entities},期望 ≥ {total}")
        return False

    print(f"✓ 入库成功: {total} chunks,Milvus total_entities={total_entities}")
    return True


# ============ 测试 3: 向量检索 ============


async def test_vector_search():
    """测试 3:向量检索(带 RBAC + 命名空间过滤)"""
    print("\n" + "=" * 60)
    print("测试 3:向量检索(带 RBAC + 命名空间过滤)")
    print("=" * 60)

    from app.rag.embeddings import get_embeddings
    from app.rag.vector_store import SearchFilter, get_vector_store

    vs = get_vector_store()
    embeddings = get_embeddings()

    # 用真实查询测试
    query = "折扣权限是怎么规定的?"
    query_emb = embeddings.embed_query(query)

    # 销售员角色,dept_sales 部门(应能查到 shared_company 文档)
    search_filter = SearchFilter(
        user_role="salesperson",
        dept_namespace="dept_sales",
        active_only=True,
    )

    results = vs.search(
        query_embedding=query_emb,
        top_k=5,
        filter=search_filter,
    )

    print(f"查询: {query}")
    print(f"检索结果数: {len(results)}")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] score={r.score:.3f}, ns={r.dept_namespace}, title={r.title[:40]}")

    if not results:
        print("✗ 检索返回 0 条(命名空间过滤可能有问题)")
        return False

    if results[0].score < 0.3:
        print(f"✗ Top-1 score 过低: {results[0].score:.3f}")
        return False

    print(f"✓ 向量检索成功:Top-1 score={results[0].score:.3f}")
    return True


# ============ 测试 4: 命名空间隔离 ============


async def test_namespace_isolation():
    """测试 4:命名空间隔离(dept_sales 不能看 restricted_exec)"""
    print("\n" + "=" * 60)
    print("测试 4:命名空间隔离")
    print("=" * 60)

    from app.rag.embeddings import get_embeddings
    from app.rag.vector_store import SearchFilter, get_vector_store

    vs = get_vector_store()
    embeddings = get_embeddings()

    query = "折扣"
    query_emb = embeddings.embed_query(query)

    # 销售员:能看 dept_sales + shared_company
    sales_filter = SearchFilter(
        user_role="salesperson",
        dept_namespace="dept_sales",
    )
    sales_results = vs.search(query_emb, top_k=10, filter=sales_filter)

    # 验证返回结果都在允许的命名空间内
    allowed_ns = {"dept_sales", "shared_company"}
    for r in sales_results:
        if r.dept_namespace not in allowed_ns:
            print(
                f"✗ 命名空间泄露:销售员看到了 {r.dept_namespace} 的文档"
            )
            return False

    print(
        f"✓ 命名空间隔离正常:销售员只看到 {allowed_ns} 内的文档,"
        f"共 {len(sales_results)} 条"
    )
    return True


# ============ 测试 5: 三级降级链 ============


async def test_degradation_chain():
    """测试 5:三级降级链(Milvus 向量 → BM25 → PG LIKE)"""
    print("\n" + "=" * 60)
    print("测试 5:三级降级链")
    print("=" * 60)

    from app.rag.degradation import DegradationChain
    from app.rag.retriever import EnterpriseRAGRetriever

    retriever = EnterpriseRAGRetriever(top_k=10, rerank_top_n=5)
    chain = DegradationChain(retriever)

    # 正常场景:Milvus 可用,应命中 vector 阶段
    result = chain.run(
        query="折扣权限",
        user_role="salesperson",
        dept_namespace="dept_sales",
        top_k=5,
    )

    print(f"stage: {result.stage}")
    print(f"结果数: {len(result.results)}")
    if result.results:
        print(f"Top-1 score: {result.results[0].score:.3f}")

    if result.stage not in ("vector", "rerank"):
        print(f"✗ 期望命中 vector/rerank 阶段,实际 {result.stage}")
        return False

    if not result.results:
        print("✗ 降级链返回 0 条结果")
        return False

    print(f"✓ 三级降级链正常:stage={result.stage},命中 {len(result.results)} 条")
    return True


# ============ 测试 6: 端到端 RAG ============


async def test_rag_e2e():
    """测试 6:KnowledgeAgent 端到端(Milvus 检索 + LLM 生成)"""
    print("\n" + "=" * 60)
    print("测试 6:端到端 RAG(Milvus 检索 + LLM 生成)")
    print("=" * 60)

    from app.agents.knowledge import KnowledgeAgent

    agent = KnowledgeAgent(
        user_role=AgentRole.SALESPERSON,
        user_dept="dept_sales",
        top_k=10,
        rerank_top_k=5,
    )

    query = "折扣权限是怎么规定的?"
    print(f"查询: {query}")

    result = await agent.run(query)

    print(f"success: {result.success}")
    print(f"confidence: {result.confidence:.3f}")
    print(f"coverage: {result.output.get('coverage')}")
    print(f"stage: {result.output.get('stage')}")
    print(f"来源数: {len(result.sources)}")
    print(f"answer(前150字): {result.output.get('answer', '')[:150]}")

    if not result.success:
        print(f"✗ RAG 失败: {result.error}")
        return False

    if result.confidence < 0.3:
        print(f"✗ 置信度过低: {result.confidence:.3f}")
        return False

    print(f"✓ 端到端 RAG 成功:confidence={result.confidence:.3f}")
    return True


# ============ 主入口 ============


async def main():
    print("=" * 60)
    print("W9-4 验证:Milvus 真实接入")
    print("=" * 60)
    print(f"VECTOR_STORE_PROVIDER = {os.environ.get('VECTOR_STORE_PROVIDER', '未设置')}")
    print(f"MILVUS_HOST = {os.environ.get('MILVUS_HOST', '未设置')}")

    # 确认环境变量
    if os.environ.get("VECTOR_STORE_PROVIDER") != "milvus":
        print("\n⚠️  VECTOR_STORE_PROVIDER 不是 milvus,本测试需要切换到 milvus")
        print("    请用以下命令运行:")
        print('    $env:VECTOR_STORE_PROVIDER="milvus"')
        print('    $env:MILVUS_HOST="localhost"')
        print("    python -m eval.run_w9_milvus")
        return

    results = {}

    tests = [
        ("milvus_init", test_milvus_init),
        ("ingest_docs", test_ingest_docs),
        ("vector_search", test_vector_search),
        ("namespace_isolation", test_namespace_isolation),
        ("degradation_chain", test_degradation_chain),
        ("rag_e2e", test_rag_e2e),
    ]

    for name, test_fn in tests:
        try:
            results[name] = await test_fn()
        except Exception as e:
            import traceback

            print(f"测试 {name} 异常: {type(e).__name__}: {e}")
            traceback.print_exc()
            results[name] = False

    # 汇总
    print("\n" + "=" * 60)
    print("W9-4 Milvus 接入验证汇总")
    print("=" * 60)
    for name, ok in results.items():
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {name}: {status}")
    print("=" * 60)

    passed = sum(1 for ok in results.values() if ok)
    print(f"通过: {passed}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
