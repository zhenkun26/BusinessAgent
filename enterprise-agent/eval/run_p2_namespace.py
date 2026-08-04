"""P2-3 验证:部门级测试数据入库 + 命名空间隔离

前置数据(已通过 ingest CLI 入库):
- eval/sample_docs/dept_sales/销售部内部激励方案.md
  → partition=dept_sales, roles=[salesperson, manager, admin], 关键词"冲刺先锋奖"
- eval/sample_docs/dept_finance/财务部预算审批细则.md
  → partition=dept_finance, roles=[finance, manager, admin], 关键词"预算冻结线"

测试内容(retriever 级,不起 API):
1. salesperson + dept_sales 检索销售激励关键词 → 命中 dept_sales chunk
2. customer_service + dept_cs 检索同样关键词 → 无 dept_sales chunk
3. finance + dept_finance 检索预算关键词 → 命中本部门;
   检索销售激励关键词 → 不命中 dept_sales
4. 降级路径隔离(缺陷 1 回归):customer_service/dept_cs 走
   KeywordRetriever 关键词降级查销售激励关键词 → 无泄露;
   同时做正对照(salesperson/dept_sales 应命中)

运行:
    python -m eval.run_p2_namespace
"""

import asyncio

from loguru import logger

# 测试期屏蔽 debug 日志,保留 info 以上
logger.remove()
logger.add(lambda m: print(m, end=""), level="WARNING")


def _print_results(results, limit=5):
    for i, r in enumerate(results[:limit], 1):
        print(f"  [{i}] score={r.score:.3f}, ns={r.dept_namespace}, title={r.title[:40]}")


# ============ 测试 1: salesperson 命中本部门文档 ============


async def test_sales_hit_own_dept():
    """测试 1:salesperson + dept_sales 检索"冲刺先锋奖"→ 命中 dept_sales chunk"""
    print("\n" + "=" * 60)
    print("测试 1:salesperson/dept_sales 检索销售激励关键词")
    print("=" * 60)

    from app.rag.retriever import EnterpriseRAGRetriever

    retriever = EnterpriseRAGRetriever(top_k=10, rerank_top_n=5)
    query = "冲刺先锋奖怎么评选,奖励多少?"
    r = retriever.retrieve(
        query=query, user_role="salesperson", dept_namespace="dept_sales"
    )

    print(f"查询: {query}")
    print(f"stage={r.stage}, 结果数={len(r.results)}")
    _print_results(r.results)

    hits = [x for x in r.results if x.dept_namespace == "dept_sales"]
    if not hits:
        print("✗ 未命中 dept_sales 的 chunk")
        return False

    print(f"✓ 命中 dept_sales chunk {len(hits)} 条")
    return True


# ============ 测试 2: customer_service 不可见销售部文档 ============


async def test_cs_isolated_from_sales():
    """测试 2:customer_service + dept_cs 检索同样关键词 → 无 dept_sales chunk"""
    print("\n" + "=" * 60)
    print("测试 2:customer_service/dept_cs 检索销售激励关键词(隔离)")
    print("=" * 60)

    from app.rag.retriever import EnterpriseRAGRetriever

    retriever = EnterpriseRAGRetriever(top_k=10, rerank_top_n=5)
    query = "冲刺先锋奖怎么评选,奖励多少?"
    r = retriever.retrieve(
        query=query, user_role="customer_service", dept_namespace="dept_cs"
    )

    print(f"查询: {query}")
    print(f"stage={r.stage}, 结果数={len(r.results)}")
    _print_results(r.results)

    leaked = [x for x in r.results if x.dept_namespace == "dept_sales"]
    if leaked:
        print(f"✗ 命名空间泄露:customer_service 看到 {len(leaked)} 条 dept_sales chunk")
        return False

    # 双保险:任何结果都不应超出允许的命名空间
    allowed = {"dept_cs", "shared_company"}
    out_of_scope = [x for x in r.results if x.dept_namespace not in allowed]
    if out_of_scope:
        print(f"✗ 越权命名空间: {[x.dept_namespace for x in out_of_scope]}")
        return False

    print(f"✓ 隔离正常:无 dept_sales chunk,结果均在 {allowed} 内")
    return True


# ============ 测试 3: finance 命中本部门且不可见销售部 ============


async def test_finance_hit_and_isolation():
    """测试 3:finance + dept_finance 命中预算细则,且看不到销售激励"""
    print("\n" + "=" * 60)
    print("测试 3:finance/dept_finance 双向验证")
    print("=" * 60)

    from app.rag.retriever import EnterpriseRAGRetriever

    retriever = EnterpriseRAGRetriever(top_k=10, rerank_top_n=5)

    # 3a. 预算关键词 → 命中 dept_finance
    query_budget = "预算冻结线触发了怎么解冻?"
    r1 = retriever.retrieve(
        query=query_budget, user_role="finance", dept_namespace="dept_finance"
    )
    print(f"查询: {query_budget}")
    print(f"stage={r1.stage}, 结果数={len(r1.results)}")
    _print_results(r1.results)

    hits = [x for x in r1.results if x.dept_namespace == "dept_finance"]
    if not hits:
        print("✗ 未命中 dept_finance 的 chunk")
        return False
    print(f"✓ 命中 dept_finance chunk {len(hits)} 条")

    # 3b. 销售激励关键词 → 不命中 dept_sales
    query_sales = "冲刺先锋奖怎么评选,奖励多少?"
    r2 = retriever.retrieve(
        query=query_sales, user_role="finance", dept_namespace="dept_finance"
    )
    print(f"查询: {query_sales}")
    print(f"stage={r2.stage}, 结果数={len(r2.results)}")
    _print_results(r2.results)

    leaked = [x for x in r2.results if x.dept_namespace == "dept_sales"]
    if leaked:
        print(f"✗ 命名空间泄露:finance 看到 {len(leaked)} 条 dept_sales chunk")
        return False

    print("✓ 隔离正常:finance 检索销售激励关键词时无 dept_sales chunk")
    return True


# ============ 测试 4: 降级路径隔离(缺陷 1 回归)============


async def test_degradation_isolation():
    """测试 4:关键词降级路径(BM25/Milvus 扫描)命名空间隔离

    缺陷 1 回归:修复前 _scan_via_milvus 缺 dept_namespace 过滤,
    customer_service 可通过降级路径看到 dept_sales 文档。
    """
    print("\n" + "=" * 60)
    print("测试 4:降级路径命名空间隔离(缺陷 1 回归)")
    print("=" * 60)

    from app.rag.degradation import KeywordRetriever

    kr = KeywordRetriever()
    keywords = ["冲刺先锋奖", "冲刺", "奖金"]

    # 4a. 反例:customer_service/dept_cs → 不得出现 dept_sales
    results_cs = kr._scan_via_milvus(
        keywords, top_k=10, user_role="customer_service", dept_namespace="dept_cs"
    )
    print(f"customer_service/dept_cs 降级扫描结果数: {len(results_cs)}")
    _print_results(results_cs)

    leaked = [x for x in results_cs if x.dept_namespace == "dept_sales"]
    if leaked:
        print(f"✗ 降级路径泄露:customer_service 看到 {len(leaked)} 条 dept_sales chunk")
        return False
    print("✓ 降级路径无 dept_sales 泄露")

    # 4b. 正对照:salesperson/dept_sales → 应命中(证明过滤没有误伤本部门)
    results_sales = kr._scan_via_milvus(
        keywords, top_k=10, user_role="salesperson", dept_namespace="dept_sales"
    )
    print(f"salesperson/dept_sales 降级扫描结果数: {len(results_sales)}")
    _print_results(results_sales)

    hits = [x for x in results_sales if x.dept_namespace == "dept_sales"]
    if not hits:
        print("✗ 正对照失败:salesperson 降级路径未命中本部门 chunk")
        return False
    print(f"✓ 正对照通过:salesperson 命中 dept_sales chunk {len(hits)} 条")

    # 4c. 链路级:retrieve_by_keywords(dept_namespace 沿调用链传入)
    results_chain = kr.retrieve_by_keywords(
        query="冲刺先锋奖怎么评选",
        top_k=10,
        user_role="customer_service",
        dept_namespace="dept_cs",
    )
    leaked_chain = [x for x in results_chain if x.dept_namespace == "dept_sales"]
    if leaked_chain:
        print(f"✗ retrieve_by_keywords 链路泄露:{len(leaked_chain)} 条 dept_sales")
        return False
    print("✓ retrieve_by_keywords 链路隔离正常")

    return True


# ============ 主入口 ============


async def main():
    print("=" * 60)
    print("P2-3 验证:部门级数据入库 + 命名空间隔离")
    print("=" * 60)

    # 初始化 Milvus(不重建,保留已入库数据)
    from app.core.milvus_client import init_milvus

    await init_milvus(recreate=False)

    results = {}

    tests = [
        ("sales_hit_own_dept", test_sales_hit_own_dept),
        ("cs_isolated_from_sales", test_cs_isolated_from_sales),
        ("finance_hit_and_isolation", test_finance_hit_and_isolation),
        ("degradation_isolation", test_degradation_isolation),
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
    print("P2-3 命名空间隔离验证汇总")
    print("=" * 60)
    for name, ok in results.items():
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {name}: {status}")
    print("=" * 60)

    passed = sum(1 for ok in results.values() if ok)
    print(f"通过: {passed}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
