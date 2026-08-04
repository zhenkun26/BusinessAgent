"""临时自测:AnalysisAgent 完整实现(W6)

用法(项目根目录):
    /d/ProgramData/anaconda3/envs/enterprise_agent/python.exe eval/_tmp_test_analysis.py

验证点:
1. salesperson 角色(有 query_order + query_customer):成功,answer 含真实数字
2. customer_service 角色(无 query_order):RBAC 拒绝

注意:会真实调用 DeepSeek API。
"""

import asyncio
import sys
from pathlib import Path

# 保证可以 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.analysis import AnalysisAgent
from app.security.rbac import AgentRole


async def test_salesperson():
    print("=" * 60)
    print("测试 1: salesperson 角色(应有权限,成功)")
    print("=" * 60)
    agent = AnalysisAgent(user_role=AgentRole.SALESPERSON)
    result = await agent.run("对比一下 C001 和 C002 两个客户的订单金额")
    print(f"success={result.success}, confidence={result.confidence}")
    print(f"stage={result.output.get('stage')}, latency={result.latency_ms}ms")
    print(f"answer 开头 100 字:\n{result.output.get('answer', '')[:100]}")
    print(f"\ndata.per_entity={result.output.get('data', {}).get('per_entity')}")
    assert result.success, "salesperson 应成功"
    assert result.output.get("stage") == "analysis_complete"
    return result


async def test_customer_service():
    print("\n" + "=" * 60)
    print("测试 2: customer_service 角色(应 RBAC 拒绝)")
    print("=" * 60)
    agent = AnalysisAgent(user_role=AgentRole.CUSTOMER_SERVICE)
    result = await agent.run("统计一下所有客户的订单金额")
    print(f"success={result.success}, stage={result.output.get('stage')}")
    print(f"answer={result.output.get('answer')}")
    assert not result.success, "customer_service 应被拒绝"
    assert result.output.get("stage") == "rbac_denied"
    return result


async def main():
    await test_salesperson()
    await test_customer_service()
    print("\n全部断言通过 [OK]")


if __name__ == "__main__":
    asyncio.run(main())
