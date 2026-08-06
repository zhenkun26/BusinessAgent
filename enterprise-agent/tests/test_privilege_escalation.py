"""权限与越权对抗性测试(security-operations 规格)

覆盖规格四个 Scenario:
1. 跨部门命名空间取数被拒绝/过滤(can_access_namespace + 降级链口径)
2. 禁用用户持旧 JWT 访问受保护接口返回 401;DB 故障降级「告警但放行」
3. 角色降级(经理→销售)后旧 token 按 DB 新角色判定权限
4. 越权使用他角色工具被 ToolGateway 拒绝
"""

from __future__ import annotations

import jwt
import pytest
from conftest import FakeResult, FakeRow, FakeSession
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger

from app.config import get_settings
from app.rag.degradation import KeywordRetriever
from app.security.rbac import (
    AgentRole,
    can_access_namespace,
    can_use_tool,
    get_current_user,
)
from app.tools.ticket import CreateTicketTool


def _make_token(role: str = "salesperson", user_id: str = "user_sales_001") -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": user_id,
            "username": "测试用户",
            "role": role,
            "department": "dept_sales",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="bearer", credentials=token)


# ============ 4.1 跨部门命名空间取数被拒绝/过滤 ============


def test_should_deny_salesperson_access_to_finance_namespace():
    """Given 销售角色, When 访问财务命名空间, Then can_access_namespace 拒绝;
    本部门与公司共享命名空间放行"""
    assert can_access_namespace(AgentRole.SALESPERSON, "dept_finance") is False
    assert can_access_namespace(AgentRole.SALESPERSON, "dept_cs") is False
    assert can_access_namespace(AgentRole.SALESPERSON, "dept_sales") is True
    assert can_access_namespace(AgentRole.SALESPERSON, "shared_company") is True
    # admin 通配
    assert can_access_namespace(AgentRole.ADMIN, "dept_finance") is True


@pytest.mark.asyncio
async def test_should_filter_other_dept_namespace_in_pg_degradation(
    monkeypatch, fake_session_factory
):
    """Given 销售用户(dept_sales)经 PG tsvector 降级链检索, When 执行查询,
    Then SQL 强制命名空间隔离(本部门 + shared_company)与角色过滤,
    不可能取到其他部门文档(降级链口径与主路径一致)"""
    session = FakeSession(responses=[FakeResult([])])
    monkeypatch.setattr(
        "app.core.database.get_session_factory", fake_session_factory(session)
    )

    retriever = KeywordRetriever()
    results = await retriever._fallback_pg_tsvector(
        ["报销", "流程"], top_k=5, user_role="salesperson", dept_namespace="dept_sales"
    )

    assert results == []
    assert session.executed_sql, "降级链应执行 PG 查询"
    sql = session.executed_sql[0]
    assert "dept_namespace IN (:dept_ns, 'shared_company')" in sql
    assert "access_roles @>" in sql
    params = session.executed_params[0]
    assert params["dept_ns"] == "dept_sales"  # 只能带本人部门,取不到 dept_finance
    assert params["role"] == '["salesperson"]'


# ============ 4.2 禁用用户持旧 JWT + 降级模式「告警但放行」 ============


@pytest.mark.asyncio
async def test_should_reject_disabled_user_holding_stale_jwt(
    monkeypatch, fake_session_factory
):
    """Given 用户被禁用但旧 JWT 未过期, When 访问受保护接口(auth_check_db=True),
    Then 返回 401(禁用即时生效)"""
    session = FakeSession(
        responses=[
            FakeResult(
                [
                    FakeRow(
                        username="销售员张三",
                        role="salesperson",
                        department="dept_sales",
                        is_active=False,
                    )
                ]
            )
        ]
    )
    monkeypatch.setattr(
        "app.core.database.get_session_factory", fake_session_factory(session)
    )
    monkeypatch.setattr(get_settings(), "auth_check_db", True)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_credentials(_make_token()))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_should_alert_but_allow_when_db_check_degraded(
    monkeypatch, fake_session_factory
):
    """Given auth_check_db=True 但数据库故障, When 持有效 JWT 访问,
    Then 降级为仅 JWT 校验:放行 + 告警(可用性优先,禁用即时性降级)"""

    class BrokenSession(FakeSession):
        async def execute(self, sql, params=None):
            raise RuntimeError("pg down")

    monkeypatch.setattr(
        "app.core.database.get_session_factory",
        fake_session_factory(BrokenSession()),
    )
    monkeypatch.setattr(get_settings(), "auth_check_db", True)

    warnings: list[str] = []
    sink_id = logger.add(lambda m: warnings.append(str(m)), level="WARNING")
    try:
        user = await get_current_user(_credentials(_make_token()))
    finally:
        logger.remove(sink_id)

    assert user.user_id == "user_sales_001"  # 放行
    assert any("降级" in w for w in warnings)  # 且告警


# ============ 4.3 角色降级后旧 token 按 DB 新角色判定 ============


@pytest.mark.asyncio
async def test_should_apply_db_role_after_role_downgrade(
    monkeypatch, fake_session_factory
):
    """Given 用户从经理降为销售(token 内仍是 manager), When 请求,
    Then 按 DB 新角色判定:解析结果为 salesperson,经理专属工具被拒"""
    session = FakeSession(
        responses=[
            FakeResult(
                [
                    FakeRow(
                        username="前经理李四",
                        role="salesperson",  # DB 已降级
                        department="dept_sales",
                        is_active=True,
                    )
                ]
            )
        ]
    )
    monkeypatch.setattr(
        "app.core.database.get_session_factory", fake_session_factory(session)
    )
    monkeypatch.setattr(get_settings(), "auth_check_db", True)

    user = await get_current_user(_credentials(_make_token(role="manager")))

    assert user.role == "salesperson"
    resolved = AgentRole(user.role)
    # 经理可用的 create_ticket/update_ticket 对销售即时失效
    assert can_use_tool(AgentRole.MANAGER, "update_ticket") is True
    assert can_use_tool(resolved, "update_ticket") is False
    assert can_access_namespace(resolved, "dept_finance") is False


# ============ 4.4 越权使用他角色工具被 ToolGateway 拒绝 ============


@pytest.mark.asyncio
async def test_should_deny_cross_role_tool_via_gateway(monkeypatch):
    """Given 销售角色调用客服专属工具 create_ticket, When 经 ToolGateway,
    Then RBAC 拒绝、不执行工具、记 security_violation 审计"""
    violations: list[dict] = []

    class FakeAuditLogger:
        async def log_violation(self, **kwargs):
            violations.append(kwargs)

    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: FakeAuditLogger())
    tool = CreateTicketTool()

    result = await tool.invoke(
        {"title": "越权工单", "content": "x", "customer_id": "C001"},
        {"role": "salesperson", "user_id": "user_sales_001"},
    )

    assert result.success is False
    assert "无权使用" in (result.error or "")
    assert violations and violations[0]["tool_name"] == "create_ticket"
    assert violations[0]["user_id"] == "user_sales_001"
