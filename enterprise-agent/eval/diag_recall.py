"""召回排序诊断:部门文档入库后,shared 文档是否被 dept chunk 挤排名

复现 P2-3 后发现的问题:
  「销售提成政策是怎么规定的」top 命中变为 dept_sales 激励方案(0.528),
  shared 销售政策仅 0.511,置信度 0.357 触发拒答/低置信提示。

输出粗排全量候选 + 精排 top5 的 (title, namespace, score),
用于判断根因是「候选池挤占」还是「排序偏移」。

用法:
    PYTHONIOENCODING=utf-8 python -m eval.diag_recall
"""

import asyncio

from app.core.milvus_client import init_milvus
from app.rag.embeddings import get_embeddings
from app.rag.reranker import get_reranker
from app.rag.vector_store import SearchFilter, get_vector_store

QUERIES = [
    "销售提成政策是怎么规定的",
    "销售提成比例是多少",
    "财务报销流程是什么",
]

ROLE = "salesperson"
DEPT = "dept_sales"


def main() -> None:
    asyncio.run(init_milvus(recreate=False))
    store = get_vector_store()
    emb = get_embeddings()
    reranker = get_reranker()

    for query in QUERIES:
        print("=" * 70)
        print(f"Query: {query}  (role={ROLE}, dept={DEPT})")
        print("=" * 70)

        qe = emb.embed_query(query)
        sf = SearchFilter(user_role=ROLE, dept_namespace=DEPT, active_only=True)
        coarse = store.search(query_embedding=qe, top_k=40, filter=sf)

        print(f"\n粗排候选({len(coarse)} 条):")
        for i, r in enumerate(coarse, 1):
            print(f"  {i:2d}. [{r.dept_namespace:15s}] {r.score:.3f}  {r.title}")

        ranked = reranker.rerank(query, coarse, top_n=5)
        print("\n精排 top5:")
        for i, r in enumerate(ranked, 1):
            print(f"  {i}. [{r.dept_namespace:15s}] {r.score:.3f}  {r.title}")
        print()


if __name__ == "__main__":
    main()
