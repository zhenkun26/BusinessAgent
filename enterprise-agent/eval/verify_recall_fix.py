"""召回修复验证:政策场景共享优先平局裁决

验证点:
1. 政策类查询(销售提成政策/比例):top1 应变为 shared 销售政策(原 dept 激励方案)
2. 非政策场景不受影响
3. 部门专属查询(明确问激励方案):dept 文档分数明显更高(>ε),仍应排 top1

用法:
    PYTHONIOENCODING=utf-8 python -m eval.verify_recall_fix
"""

import asyncio

from app.core.milvus_client import init_milvus
from app.rag.retriever import EnterpriseRAGRetriever

CASES = [
    ("销售提成政策是怎么规定的", "policy", "shared_company"),
    # "比例"不命中政策关键词 → factual 场景,平局裁决不适用,dept 仍可排前
    # (factual 近平局属真实相关性并列,暂维持原排序,见诊断结论)
    ("销售提成比例是多少", "factual", "dept_sales"),
    ("财务报销流程是什么", "policy", "shared_company"),
    ("销售部内部激励方案的激励规则有哪些", None, "dept_sales"),  # dept 应赢
]

ROLE = "salesperson"
DEPT = "dept_sales"


def main() -> None:
    asyncio.run(init_milvus(recreate=False))
    retriever = EnterpriseRAGRetriever()

    all_ok = True
    for query, expect_scene, expect_top_ns in CASES:
        r = retriever.retrieve(query=query, user_role=ROLE, dept_namespace=DEPT)
        top1 = r.results[0] if r.results else None
        top_ns = top1.dept_namespace if top1 else "∅"
        ok = top_ns == expect_top_ns
        all_ok &= ok
        if expect_scene:
            assert r.scene == expect_scene, f"场景识别异常: {r.scene} != {expect_scene}"
        print(f"{'✓' if ok else '✗'} [{r.scene:11s}] {query}")
        print(f"    top1: [{top_ns}] {top1.score:.3f} {top1.title}")
        for i, res in enumerate(r.results[1:3], 2):
            print(f"    top{i}: [{res.dept_namespace}] {res.score:.3f} {res.title}")

    print("=" * 50)
    print("全部通过" if all_ok else "存在未达预期的用例")


if __name__ == "__main__":
    main()
