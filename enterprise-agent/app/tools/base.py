"""ToolGateway 抽象层 + 工具注册表(对应 v3 方案 6.5 节)

设计目标:
- 统一工具调用入口:权限校验 → 参数校验 → 调用外部 API → 返回标准化结果
- 业务系统 API 暂用 Mock(W7 阶段无真实系统对接),接口契约完整
- 切换真实 API:子类覆盖 _call_external 即可,业务层无感知
- 支持补偿回滚:有副作用的工具需实现 compensate 方法(Saga 用)

工具分类:
- 查询类(无副作用):query_customer / query_order / query_ticket / query_my_approvals
- 操作类(有副作用,需 Saga 补偿):create_crm_task / send_email / create_ticket / update_ticket
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger

from app.observability.audit import get_audit_logger
from app.observability.tracing import (
    record_span_attributes,
    record_span_event,
    traced_span,
)
from app.security.rbac import AgentRole, can_use_tool


# ============ 工具分类 ============


class ToolCategory(str, Enum):
    """工具分类(决定是否需要 Saga 补偿)"""

    QUERY = "query"  # 查询类,无副作用,无需补偿
    ACTION = "action"  # 操作类,有副作用,需 Saga 补偿


# ============ 工具结果数据契约 ============


@dataclass
class ToolResult:
    """工具调用标准结果"""

    success: bool
    tool_name: str
    output: dict[str, Any]  # 工具输出数据
    error: Optional[str] = None
    latency_ms: int = 0
    # Saga 补偿用:记录已产生的副作用,供回滚时使用
    side_effects: dict[str, Any] = field(default_factory=dict)
    # 补偿上下文:compensate 方法用此数据回滚
    compensation_data: dict[str, Any] = field(default_factory=dict)


# ============ ToolGateway 抽象基类 ============


class BaseTool(ABC):
    """工具抽象基类

    子类需实现:
    - name: 工具名(唯一标识,对应 RBAC ROLE_TOOLS)
    - category: 工具分类(QUERY/ACTION)
    - description: 工具描述(供 LLM 工具选择用)
    - input_schema: 入参 Pydantic Model 类
    - _execute: 实际执行逻辑(含 Mock 或真实 API 调用)
    - compensate(仅 ACTION 类需实现): 补偿回滚逻辑
    """

    # 子类必须覆盖的类属性
    name: str = ""
    category: ToolCategory = ToolCategory.QUERY
    description: str = ""
    # 风险等级(low / medium / high),审批建单时取最高值
    risk_level: str = "low"
    # 是否需要审批(如外部邮件等高风险操作,True 时执行前先建审批单)
    requires_approval: bool = False

    @abstractmethod
    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        """实际执行逻辑(子类实现)

        Args:
            params: 入参(已通过 input_schema 校验)
            context: 调用上下文(user_id, role, dept, jwt_token, request_id)

        Returns:
            ToolResult
        """
        ...

    async def compensate(self, compensation_data: dict[str, Any]) -> ToolResult:
        """补偿回滚(仅 ACTION 类需实现)

        默认实现:返回成功(无副作用工具无需补偿)
        ACTION 类工具如需回滚,覆盖此方法。

        Args:
            compensation_data: 执行时记录的补偿上下文
        """
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message": f"工具 {self.name} 无补偿逻辑(默认成功)"},
        )

    # ============ 公共入口(业务层调用)============

    async def invoke(
        self,
        params: dict[str, Any],
        context: dict[str, Any],
        skip_rbac: bool = False,
    ) -> ToolResult:
        """工具调用入口(统一权限校验 + 参数校验 + 执行 + 日志 + tracing)

        Args:
            params: 入参字典
            context: 调用上下文(必须含 role 字段)
            skip_rbac: 跳过 RBAC 校验(仅内部调用用,如 Saga 补偿)

        Returns:
            ToolResult
        """
        start = time.time()
        tool_name = self.name
        role_str = context.get("role", "unknown")

        # tracing: 整个工具调用作为 span
        with traced_span(
            f"tool.{tool_name}",
            attributes={
                "tool.name": tool_name,
                "tool.category": self.category.value,
                "tool.role": role_str,
                "tool.skip_rbac": skip_rbac,
            },
        ):
            # 1. RBAC 权限校验
            if not skip_rbac:
                try:
                    role = AgentRole(role_str) if isinstance(role_str, str) else role_str
                except ValueError:
                    record_span_event("rbac.unknown_role", {"role": role_str})
                    return ToolResult(
                        success=False,
                        tool_name=tool_name,
                        output={},
                        error=f"未知角色: {role_str}",
                        latency_ms=int((time.time() - start) * 1000),
                    )

                if not can_use_tool(role, tool_name):
                    logger.warning(f"工具权限拒绝: role={role.value}, tool={tool_name}")
                    record_span_event("rbac.denied", {"role": role.value, "tool": tool_name})
                    # 审计:RBAC 越权尝试
                    await get_audit_logger().log_violation(
                        user_id=context.get("user_id"),
                        tool_name=tool_name,
                        reason=f"角色 {role.value} 无权使用工具 {tool_name}",
                    )
                    return ToolResult(
                        success=False,
                        tool_name=tool_name,
                        output={},
                        error=f"角色 {role.value} 无权使用工具 {tool_name}",
                        latency_ms=int((time.time() - start) * 1000),
                    )

            # 2. 参数校验(子类的 input_schema)
            try:
                validated_params = self._validate_params(params)
            except Exception as e:
                record_span_event("param.invalid", {"error": str(e)})
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    output={},
                    error=f"参数校验失败: {e}",
                    latency_ms=int((time.time() - start) * 1000),
                )

            # 3. Prompt 注入防护
            injection_check = self._check_injection(validated_params)
            if injection_check:
                logger.warning(f"Prompt 注入检测: tool={tool_name}, risk={injection_check}")
                record_span_event("security.injection_detected", {"risk": injection_check})
                # 审计:注入攻击尝试
                await get_audit_logger().log_violation(
                    user_id=context.get("user_id"),
                    tool_name=tool_name,
                    reason=injection_check,
                )
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    output={},
                    error=f"输入存在安全风险: {injection_check}",
                    latency_ms=int((time.time() - start) * 1000),
                )

            # 4. 执行
            try:
                logger.info(
                    f"工具调用: tool={tool_name}, role={role_str}, "
                    f"params_keys={list(validated_params.keys())}"
                )
                result = await self._execute(validated_params, context)
                result.latency_ms = int((time.time() - start) * 1000)

                record_span_attributes({
                    "tool.success": result.success,
                    "tool.latency_ms": result.latency_ms,
                })

                # 审计:工具调用结果(AuditLogger 自身容错,失败不阻塞)
                # payload 透传审批触发标记:审批触发的执行 user_id=发起人,
                # 但 payload.triggered_by="approval" + approval_id 可区分于主动调用
                audit_payload: dict = {
                    "role": role_str,
                }
                if context.get("triggered_by"):
                    audit_payload["triggered_by"] = context["triggered_by"]
                if context.get("approval_id"):
                    audit_payload["approval_id"] = context["approval_id"]
                await get_audit_logger().log_tool_call(
                    session_id=context.get("session_id"),
                    user_id=context.get("user_id"),
                    tool_name=tool_name,
                    input_summary=str(validated_params)[:500],
                    output_summary=str(result.output)[:500],
                    success=result.success,
                    latency_ms=result.latency_ms,
                    payload=audit_payload,
                )

                logger.info(
                    f"工具完成: tool={tool_name}, success={result.success}, "
                    f"latency={result.latency_ms}ms"
                )
                return result

            except Exception as e:  # noqa: BLE001
                logger.exception(f"工具执行异常: tool={tool_name}, error={e}")
                from app.observability.tracing import record_exception
                record_exception(e)
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    output={},
                    error=f"工具执行异常: {type(e).__name__}: {e}",
                    latency_ms=int((time.time() - start) * 1000),
                )

    # ============ 辅助方法 ============

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """用 input_schema 校验入参

        子类如有 input_schema 类属性,会自动校验并返回 dict。
        无 input_schema 时直接返回原 params。
        """
        schema_cls = getattr(self, "input_schema", None)
        if schema_cls is None:
            return params

        # Pydantic Model 校验
        instance = schema_cls(**params)
        return instance.model_dump(exclude_none=True)

    @staticmethod
    def _check_injection(params: dict[str, Any]) -> Optional[str]:
        """Prompt 注入检测(简单规则,可扩展)

        检测常见注入模式:
        - 系统提示词覆盖: "ignore previous", "disregard", "system:"
        - 越权指令: "as admin", "you are", "pretend"
        - 代码注入: "eval(", "exec(", "__import__"

        Returns:
            风险描述(None 表示无风险)
        """
        injection_patterns = [
            ("ignore previous", "系统提示覆盖"),
            ("disregard above", "系统提示覆盖"),
            ("system:", "系统提示覆盖"),
            ("you are now", "身份劫持"),
            ("pretend you are", "身份劫持"),
            ("as an admin", "越权指令"),
            ("eval(", "代码注入"),
            ("exec(", "代码注入"),
            ("__import__", "代码注入"),
            ("rm -rf", "危险命令"),
        ]

        def _scan(value: Any) -> Optional[str]:
            if isinstance(value, str):
                lowered = value.lower()
                for pattern, risk_type in injection_patterns:
                    if pattern in lowered:
                        return f"{risk_type}: 检测到 '{pattern}'"
            elif isinstance(value, dict):
                for v in value.values():
                    risk = _scan(v)
                    if risk:
                        return risk
            elif isinstance(value, list):
                for v in value:
                    risk = _scan(v)
                    if risk:
                        return risk
            return None

        return _scan(params)


# ============ 工具注册表 ============


_tool_registry: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool) -> None:
    """注册工具到全局注册表"""
    if not tool.name:
        raise ValueError(f"工具 {type(tool).__name__} 未定义 name 属性")
    if tool.name in _tool_registry:
        logger.warning(f"工具 {tool.name} 已注册,覆盖旧实例")
    _tool_registry[tool.name] = tool
    logger.info(f"工具注册: {tool.name} ({tool.category.value})")


def get_tool(name: str) -> Optional[BaseTool]:
    """从注册表获取工具"""
    return _tool_registry.get(name)


def list_tools() -> list[dict[str, str]]:
    """列出所有已注册工具(供 LLM 工具选择用)"""
    return [
        {
            "name": t.name,
            "category": t.category.value,
            "description": t.description,
        }
        for t in _tool_registry.values()
    ]


def init_all_tools() -> None:
    """初始化并注册所有内置工具(应用启动时调用)"""
    from app.tools.approval import QueryMyApprovalsTool
    from app.tools.crm import CreateCrmTaskTool, QueryCustomerTool, QueryOrderTool
    from app.tools.mail import SendEmailInternalTool, SendEmailExternalTool
    from app.tools.ticket import CreateTicketTool, UpdateTicketTool

    tools = [
        QueryCustomerTool(),
        QueryOrderTool(),
        CreateCrmTaskTool(),
        SendEmailInternalTool(),
        SendEmailExternalTool(),
        CreateTicketTool(),
        UpdateTicketTool(),
        QueryMyApprovalsTool(),
    ]
    for tool in tools:
        register_tool(tool)

    logger.info(f"工具初始化完成,共 {len(_tool_registry)} 个工具")
