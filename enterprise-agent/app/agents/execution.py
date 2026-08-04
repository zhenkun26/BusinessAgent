"""ExecutionAgent:工具执行 Agent(W7 完整实现)

职责：
- 解析用户工具调用意图(LLM 提取工具名 + 参数)
- 单工具调用：直接走 ToolGateway
- 多工具调用：走 Saga 协调器(保证补偿一致性)
- RBAC 权限校验(在 ToolGateway 层)
- 返回结构化 AgentResult

对应 v3 方案 6.5 节

LLM 工具选择策略：
- 注入可用工具列表(根据 user_role 过滤)到 prompt
- LLM 输出 JSON: [{"tool": "...", "params": {...}}, ...]
- 失败降级：关键词匹配(如"发邮件"→send_email_internal)
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from loguru import logger
from pydantic import BaseModel, Field

from app.agents.knowledge import AgentResult
from app.observability.audit import get_audit_logger
from app.rag.llm import get_lite_llm
from app.security.rbac import AgentRole, ROLE_TOOLS
from app.tools.base import ToolResult, get_tool, init_all_tools, list_tools
from app.tools.saga import SagaCoordinator, SagaResult


# ============ 工具初始化标志 ============

_tools_initialized = False


def _ensure_tools():
    """确保工具已注册(懒加载，首次调用时初始化)"""
    global _tools_initialized
    if not _tools_initialized:
        init_all_tools()
        _tools_initialized = True


# ============ LLM 工具选择(P2-1:prompt 从注册表获取) ============

from app.prompts import get_prompt

# 关键词降级映射(LLM 失败时用)
KEYWORD_TOOL_MAP = {
    "发邮件": "send_email_internal",
    "发内部邮件": "send_email_internal",
    "发外部邮件": "send_email_external",
    "创建工单": "create_ticket",
    "更新工单": "update_ticket",
    "查客户": "query_customer",
    "查订单": "query_order",
    "创建跟进": "create_crm_task",
    "创建crm": "create_crm_task",
    # 宽匹配兜底(放最后,具体词优先):「发一封邮件」等变体不含「发邮件」子串,
    # 本地小模型返回空工具列表时,靠它接住(LLM 工具选择失败的最后防线)
    "邮件": "send_email_internal",
}


# ============ 工具调用计划 ============


def _param_spec(tool_name: str) -> str:
    """生成工具的参数说明片段(注入工具选择 prompt)

    本地小模型(qwen3.5:4b)看不到 pydantic schema 时会瞎猜参数名
    (实测把 to/body 猜成 recipient/content、漏填必填的 title/assignee),
    把字段名 + 必填标记 + 字段描述显式注入后参数抽取才稳定。
    """
    tool = get_tool(tool_name)
    schema = getattr(tool, "input_schema", None) if tool else None
    if schema is None:
        return ""
    required = set(schema.model_json_schema().get("required", []))
    parts = []
    for fname, finfo in schema.model_fields.items():
        req = "必填" if fname in required else "可选"
        desc = finfo.description or ""
        parts.append(f"{fname}({req}{',' + desc if desc else ''})")
    return f" 参数： {'; '.join(parts)}" if parts else ""


class ToolCallPlan(BaseModel):
    """单个工具调用计划"""

    tool: str = Field(description="工具名")
    params: dict[str, Any] = Field(default_factory=dict, description="工具参数")
    reason: str = Field(default="", description="调用原因")


# ============ 公共执行入口(审批批准后复用)============


async def execute_tool_calls(
    plans: list[ToolCallPlan], context: dict[str, Any]
) -> ToolResult | SagaResult:
    """执行工具调用计划：单工具直接调用，多工具走 Saga 协调器

    供 ExecutionAgent.run 与审批批准后的服务端同步执行(app.api.approval)复用。

    Args:
        plans: 工具调用计划列表(应已过 RBAC 过滤)
        context: 调用上下文(user_id/role/dept/jwt_token/request_id/session_id)

    Returns:
        单工具返回 ToolResult，多工具返回 SagaResult
    """
    _ensure_tools()
    if len(plans) == 1:
        return await _invoke_single(plans[0], context)
    return await _invoke_saga(plans, context)


async def _invoke_single(
    plan: ToolCallPlan, context: dict[str, Any]
) -> ToolResult:
    """单工具直接调用"""
    tool = get_tool(plan.tool)
    if tool is None:
        return ToolResult(
            success=False,
            tool_name=plan.tool,
            output={},
            error=f"工具未注册： {plan.tool}",
        )

    return await tool.invoke(plan.params, context)


async def _invoke_saga(
    plans: list[ToolCallPlan], context: dict[str, Any]
) -> SagaResult:
    """多工具走 Saga 协调器(顺序执行 + 失败补偿)"""
    saga = SagaCoordinator(context=context)

    for i, plan in enumerate(plans, start=1):
        step_id = f"step{i}"
        # 查询类工具失败不阻断(可继续后续步骤)
        tool = get_tool(plan.tool)
        block = True
        if tool and tool.category.value == "query":
            block = False

        saga.add_step(
            step_id=step_id,
            tool_name=plan.tool,
            params=plan.params,
            block_on_failure=block,
        )

    return await saga.execute()


# ============ ExecutionAgent ============


class ExecutionAgent:
    """工具执行 Agent(W7 完整实现)

    流程：
    1. 确保工具已注册
    2. LLM 解析用户消息 → 工具调用计划列表
    3. 过滤 RBAC 无权限的工具
    4. 拆分：requires_approval 的工具先建审批单(批准后自动执行)，其余直接执行
    5. 单工具：直接调用 ToolGateway；多工具：Saga 协调器顺序执行 + 补偿
    6. 返回 AgentResult
    """

    def __init__(
        self,
        user_role: AgentRole,
        user_dept: Optional[str] = None,
        llm=None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        jwt_token: str = "",
    ):
        self.user_role = user_role
        self.user_dept = user_dept
        self.llm = llm  # 懒加载
        # 调用身份(审批建单/审计用),由 executor 从 UserInput 注入
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.jwt_token = jwt_token

    def _get_llm(self):
        if self.llm is None:
            self.llm = get_lite_llm()
        return self.llm

    async def run(self, query: str) -> AgentResult:
        """执行工具调用"""
        start = time.time()
        _ensure_tools()

        # 构造调用上下文
        context = {
            "user_id": self.user_id or "system",  # 由外层注入真实 user_id
            "role": self.user_role.value if hasattr(self.user_role, "value") else str(self.user_role),
            "dept": self.user_dept or "shared_company",
            "jwt_token": self.jwt_token,
            "session_id": self.conversation_id,
            "request_id": f"exec-{int(start)}",
        }

        logger.info(f"ExecutionAgent 开始： query={query[:80]!r}, role={context['role']}")

        try:
            # 1. LLM 解析工具调用计划
            plans = await self._parse_tool_calls(query, context["role"])

            if not plans:
                # 无工具调用需求
                latency_ms = int((time.time() - start) * 1000)
                return AgentResult(
                    agent_name="execution",
                    success=False,
                    confidence=0.0,
                    output={
                        "answer": "未识别到需要执行的工具操作。如需查询知识请直接提问，如需执行操作请明确说明(如'给XX发邮件')。",
                        "coverage": "none",
                        "stage": "no_tool_detected",
                    },
                    sources=[],
                    latency_ms=latency_ms,
                    needs_replan=False,
                )

            # 1.5 内外邮件地址纠偏:内部工具 + 外部地址 → 改挂外部工具
            # LLM/关键词都可能把外部邮件错挂到内部工具;不纠偏的话,有内部权限的
            # 角色会绕过 RBAC 直到工具层才报「不允许外部地址」。纠偏后:
            # 无外部权限 → RBAC 友好拒绝;有权限 → 正常走高风险审批流
            for p in plans:
                if p.tool == "send_email_internal":
                    to_list = p.params.get("to") or []
                    if isinstance(to_list, str):
                        to_list = [to_list]
                    if any(
                        isinstance(a, str) and "@" in a and not a.endswith("@company.internal")
                        for a in to_list
                    ):
                        logger.info("内部邮件含外部地址，纠偏为 send_email_external")
                        p.tool = "send_email_external"

            # 2. RBAC 过滤
            allowed_tools = ROLE_TOOLS.get(self.user_role, [])
            filtered = []
            for p in plans:
                if p.tool in allowed_tools:
                    filtered.append(p)
                else:
                    logger.warning(
                        f"RBAC 拒绝工具： role={context['role']}, tool={p.tool}"
                    )

            if not filtered:
                latency_ms = int((time.time() - start) * 1000)
                return AgentResult(
                    agent_name="execution",
                    success=False,
                    confidence=0.0,
                    output={
                        "answer": f"您的角色({context['role']})无权执行所需工具。请联系管理员申请权限。",
                        "coverage": "none",
                        "stage": "rbac_denied",
                        "requested_tools": [p.tool for p in plans],
                    },
                    sources=[],
                    latency_ms=latency_ms,
                    needs_replan=False,
                )

            # 3. 拆分:需审批的工具先建审批单(批准后自动执行),其余照常执行
            approval_plans: list[ToolCallPlan] = []
            direct_plans: list[ToolCallPlan] = []
            for p in filtered:
                tool = get_tool(p.tool)
                if tool is not None and tool.requires_approval:
                    approval_plans.append(p)
                else:
                    direct_plans.append(p)

            # 3.5 审批参数预校验:关键参数缺失/非法(如外部邮件空收件人 to=[])不建单。
            # 审批负载建单即冻结,缺参批准后执行必失败(状态还落「已执行」),
            # 这里前置拦截,引导用户补齐信息后再发起。
            param_issues: list[str] = []
            if approval_plans:
                still_valid: list[ToolCallPlan] = []
                for p in approval_plans:
                    tool = get_tool(p.tool)
                    try:
                        if tool is not None:
                            tool._validate_params(p.params)
                        still_valid.append(p)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            f"审批参数不完整，不建单： tool={p.tool}, err={e}"
                        )
                        param_issues.append(p.tool)
                approval_plans = still_valid

            # 审批建单(建单挂起,批准后服务端同步执行 prefill_payload)
            approval_ids: list[str] = []
            approval_note = ""
            if approval_plans:
                try:
                    approval_id = await self._create_approval_request(
                        approval_plans, context, query
                    )
                    approval_ids.append(approval_id)
                    approval_note = (
                        f"以下操作已提交审批(审批号 {approval_id})，"
                        f"待经理审批后自动执行： "
                        + ", ".join(p.tool for p in approval_plans)
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception(f"审批建单失败： {e}")
                    approval_note = f"审批建单失败： {e}"

            # 4. 执行无需审批的部分:单工具直接调用,多工具走 Saga
            result = None
            if direct_plans:
                result = await execute_tool_calls(direct_plans, context)

            latency_ms = int((time.time() - start) * 1000)

            # 参数不全被拦截的审批项:给出引导话术
            issue_note = ""
            if param_issues:
                issue_note = (
                    "以下操作缺少必要信息(如收件人邮箱)，暂未提交审批： "
                    + ", ".join(param_issues)
                    + "。请补充完整信息后再试，或先让我帮你查一下相关客户/联系人。"
                )

            # 5. 构造 AgentResult(合并已执行结果与审批说明)
            if result is not None:
                success = result.success
                answer = self._format_answer(direct_plans, result)
                stage = "saga" if len(direct_plans) > 1 else "single"
            else:
                # 只有审批项:挂起等待审批
                success = bool(approval_ids)
                answer = ""
                stage = "approval_pending"
                if param_issues and not approval_ids:
                    stage = "missing_params"

            if approval_note:
                answer = f"{answer}\n{approval_note}".strip()
            if issue_note:
                answer = f"{answer}\n{issue_note}".strip()

            return AgentResult(
                agent_name="execution",
                success=success,
                confidence=0.9 if success else 0.3,
                output={
                    "answer": answer,
                    "coverage": "full" if success else "partial",
                    "stage": stage,
                    "tool_calls": [
                        {
                            "tool": p.tool,
                            "params": p.params,
                            "reason": p.reason,
                        }
                        for p in filtered
                    ],
                    "approval_ids": approval_ids,
                    "pending_approval_tools": [p.tool for p in approval_plans],
                    "saga_compensated": getattr(result, "compensated", False),
                    "saga_errors": getattr(result, "compensation_errors", []),
                    "outputs": getattr(result, "outputs", {}),
                },
                sources=[],
                latency_ms=latency_ms,
                needs_replan=False,
                replan_reason=None,
            )

        except Exception as e:  # noqa: BLE001
            logger.exception(f"ExecutionAgent 异常： {e}")
            return AgentResult(
                agent_name="execution",
                success=False,
                confidence=0.0,
                output={
                    "answer": f"工具执行异常： {e}",
                    "coverage": "none",
                    "stage": "error",
                },
                sources=[],
                error=str(e),
                latency_ms=int((time.time() - start) * 1000),
            )

    # ============ LLM 工具选择 ============

    async def _parse_tool_calls(self, query: str, role: str) -> list[ToolCallPlan]:
        """LLM 解析用户消息，提取工具调用计划

        失败降级：关键词匹配
        """
        # 构造可用工具列表(按 role 过滤)
        allowed_tools = ROLE_TOOLS.get(self.user_role, [])
        all_tools = list_tools()
        available = [t for t in all_tools if t["name"] in allowed_tools]

        if not available:
            logger.warning(f"角色 {role} 无可用工具")
            return []

        tools_desc = "\n".join(
            f"- {t['name']}: {t['description']} (类别： {t['category']}){_param_spec(t['name'])}"
            for t in available
        )

        # LLM 解析:云端 flash 优先,本地 qwen 兜底(2026-07-28 调整)
        # 背景:本地 4B 会返回"合法 JSON 但选错工具"(实测发外部邮件话术稳定
        # 只选 query_customer,漏掉 send_email_external),此时旧回退(仅本地
        # 失败/返回空才上云)不触发,审批单建不出来。工具选择是 4B 最弱环节,
        # 直接云端优先;云端不可用或返回空再走本地,最后关键词兜底
        tpl, pv = get_prompt("execution_tool_selection")
        logger.debug(f"prompt=execution_tool_selection v{pv}")
        prompt = tpl.format(tools=tools_desc, message=query)

        llm = self._get_llm()
        candidates: list[tuple[str, Any]] = []
        from langchain_ollama import ChatOllama

        if isinstance(llm, ChatOllama):
            from app.rag.llm import get_cloud_lite_llm

            cloud = get_cloud_lite_llm()
            if cloud is not None:
                candidates.append(("云端flash", cloud))
        candidates.append(("本地", llm))

        for name, model in candidates:
            try:
                resp = await model.ainvoke([HumanMessage(content=prompt)])
                text = resp.content if hasattr(resp, "content") else str(resp)
                plans = self._parse_llm_response(text)
                if plans:
                    logger.info(f"LLM 工具选择成功({name}): {len(plans)} 个工具调用")
                    return plans
                logger.info(f"{name}返回空工具列表")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{name}工具选择失败： {e}")

        # 降级:关键词匹配
        return self._keyword_fallback(query)

    @staticmethod
    def _parse_llm_response(text: str) -> list[ToolCallPlan]:
        """解析 LLM 输出的 JSON 工具调用列表"""
        # 提取 JSON 数组(兼容 markdown 代码块包裹)
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
            if not isinstance(data, list):
                return []

            plans = []
            for item in data:
                if not isinstance(item, dict) or "tool" not in item:
                    continue
                plans.append(
                    ToolCallPlan(
                        tool=item["tool"],
                        params=item.get("params", {}),
                        reason=item.get("reason", ""),
                    )
                )
            return plans
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _keyword_fallback(query: str) -> list[ToolCallPlan]:
        """关键词降级匹配"""
        lowered = query.lower()
        for keyword, tool_name in KEYWORD_TOOL_MAP.items():
            if keyword in lowered:
                # 内外邮件区分:宽匹配「邮件」命中内部工具,但消息明确说「外部」时
                # 改映射外部工具——让 RBAC 能正确拦截(销售员拿到友好拒绝),
                # 而不是内部工具在参数校验时才报「不允许外部地址」
                if tool_name == "send_email_internal" and "外部" in query:
                    tool_name = "send_email_external"
                # 简单参数构造(实际场景可更精细)
                params: dict[str, Any] = {}
                if "email" in tool_name or "邮件" in keyword:
                    params = {
                        "to": ["colleague@company.internal"],
                        "subject": "自动生成的邮件",
                        "body": query,
                    }
                elif "ticket" in tool_name or "工单" in keyword:
                    params = {
                        "title": query[:100],
                        "description": query,
                        "priority": "normal",
                    }
                elif "customer" in tool_name:
                    params = {"customer_id": "C001"}
                elif "order" in tool_name:
                    params = {"order_id": "ORD-2026-001"}
                elif "crm" in tool_name:
                    params = {
                        "customer_id": "C001",
                        "title": query[:100],
                        "assignee": "u001",
                    }

                return [ToolCallPlan(tool=tool_name, params=params, reason=f"关键词匹配： {keyword}")]

        return []

    # ============ 执行 ============

    async def _execute_single(
        self, plan: ToolCallPlan, context: dict[str, Any]
    ) -> ToolResult:
        """单工具直接调用(委托模块级实现，供 execute_tool_calls 复用)"""
        return await _invoke_single(plan, context)

    async def _execute_saga(
        self, plans: list[ToolCallPlan], context: dict[str, Any]
    ) -> SagaResult:
        """多工具走 Saga 协调器(委托模块级实现)"""
        return await _invoke_saga(plans, context)

    # ============ 审批建单(requires_approval 工具)============

    async def _create_approval_request(
        self,
        plans: list[ToolCallPlan],
        context: dict[str, Any],
        query: str,
    ) -> str:
        """为需审批的工具调用创建审批单(status=pending)，返回 approval_id

        - 先 upsert sessions 行(approval_requests.session_id 外键依赖)
        - prefill_payload 保存完整工具调用计划，批准后服务端据此同步执行
        - 有效期 1 天，审批角色： manager/admin
        """
        from sqlalchemy import text

        from app.core.database import get_session_factory

        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        session_id = context.get("session_id") or (
            f"sess_{context.get('user_id', 'system')}_{uuid.uuid4().hex[:8]}"
        )
        context["session_id"] = session_id  # 回填,保证审计 session 一致
        user_id = context.get("user_id") or "system"

        # 风险等级取所有工具中的最高值
        risk_rank = {"low": 0, "medium": 1, "high": 2}
        risk_level = "low"
        for p in plans:
            tool = get_tool(p.tool)
            tool_risk = getattr(tool, "risk_level", "low") if tool else "low"
            if risk_rank.get(tool_risk, 0) > risk_rank.get(risk_level, 0):
                risk_level = tool_risk

        prefill_payload = {
            "tool_calls": [
                {"tool": p.tool, "params": p.params, "reason": p.reason}
                for p in plans
            ]
        }

        factory = get_session_factory()
        async with factory() as session:
            # upsert 会话行(chat 不写 sessions 表,此处补外键依赖)
            await session.execute(
                text(
                    "INSERT INTO sessions (session_id, user_id, original_query, status) "
                    "VALUES (:sid, :uid, :query, 'running') "
                    "ON CONFLICT (session_id) DO NOTHING"
                ),
                {"sid": session_id, "uid": user_id, "query": query[:500]},
            )
            await session.execute(
                text(
                    "INSERT INTO approval_requests ("
                    "approval_id, session_id, requester_id, operation_type, "
                    "risk_level, summary, prefill_payload, approver_roles, "
                    "status, requester_token, expires_at"
                    ") VALUES ("
                    ":aid, :sid, :uid, :op, :risk, :summary, "
                    "CAST(:payload AS JSONB), CAST(:roles AS JSONB), "
                    "'pending', :token, NOW() + INTERVAL '1 day'"
                    ")"
                ),
                {
                    "aid": approval_id,
                    "sid": session_id,
                    "uid": user_id,
                    "op": plans[0].tool,
                    "risk": risk_level,
                    "summary": self._build_approval_summary(plans, query),
                    "payload": json.dumps(prefill_payload, ensure_ascii=False),
                    "roles": json.dumps(["manager", "admin"]),
                    "token": context.get("jwt_token") or "",
                },
            )
            await session.commit()

        logger.info(
            f"审批建单完成： approval_id={approval_id}, "
            f"tools={[p.tool for p in plans]}, risk={risk_level}"
        )

        # 审计:审批单创建
        await get_audit_logger().log(
            event_type="approval_created",
            user_id=user_id,
            session_id=session_id,
            payload={
                "approval_id": approval_id,
                "tools": [p.tool for p in plans],
                "risk_level": risk_level,
            },
        )

        return approval_id

    @staticmethod
    def _build_approval_summary(plans: list[ToolCallPlan], query: str) -> str:
        """构造人读审批摘要(如"向 X 发送外部邮件")"""
        parts = []
        for p in plans:
            to_list = p.params.get("to")
            if isinstance(to_list, str):
                to_list = [to_list]  # LLM 可能输出单字符串,统一为列表避免逐字符 join
            if "email" in p.tool and to_list:
                recipients = ", ".join(str(t) for t in to_list[:3])
                subject = p.params.get("subject", "")
                parts.append(f"向 {recipients} 发送邮件「{subject[:50]}」")
            else:
                parts.append(f"{p.tool}: {p.reason or query[:50]}")
        return ";".join(parts)[:500]

    # ============ 结果格式化 ============

    @staticmethod
    def _money(v) -> str:
        try:
            return f"{float(v):,.0f} 元"
        except (TypeError, ValueError):
            return str(v)

    @classmethod
    def _fmt_tool_output(cls, tool_name: str, output: dict) -> str:
        """按工具类型把结构化输出格式化为 markdown 话术(不再透传原始 dict)"""
        if not isinstance(output, dict) or not output:
            return "执行成功。"

        if tool_name == "query_customer":
            c = output.get("customer") or {}
            if not c:
                return "未查询到客户信息。"
            lines = [f"**{c.get('name', '')}**({c.get('customer_id', '')})"]
            if c.get("level"):
                lines[0] += f" · 等级 **{c['level']}**"
            if c.get("contact"):
                lines.append(f"- 联系人：{c['contact']}" + (f" {c['phone']}" if c.get("phone") else ""))
            if c.get("email"):
                lines.append(f"- 邮箱：{c['email']}")
            if c.get("industry"):
                lines.append(f"- 行业：{c['industry']}")
            if c.get("total_revenue") is not None:
                lines.append(f"- 累计销售额：{cls._money(c['total_revenue'])}")
            return "\n".join(lines)

        if tool_name == "query_order":
            o = output.get("order") or {}
            if not o:
                return "未查询到订单信息。"
            lines = [f"**订单 {o.get('order_id', '')}** · 客户 {o.get('customer_id', '')} · 状态 **{o.get('status', '')}**"]
            if o.get("amount") is not None:
                lines.append(f"- 金额：{cls._money(o['amount'])}")
            if o.get("created_at"):
                lines.append(f"- 创建日期：{o['created_at']}")
            items = o.get("items") or []
            if items:
                skus = "、".join(str(i.get("sku", i)) for i in items)
                lines.append(f"- 明细：{skus}")
            return "\n".join(lines)

        if tool_name == "create_crm_task":
            t = output.get("task") or {}
            if not t:
                return "回访任务已创建。"
            lines = [f"回访任务已创建：**{t.get('title', '')}**(任务号 `{t.get('task_id', '')}`)"]
            lines.append(f"- 关联客户：{t.get('customer_id', '')} · 负责人：{t.get('assignee', '')}")
            lines.append(f"- 优先级：{t.get('priority', '')} · 状态：{t.get('status', '')}")
            if t.get("due_date"):
                lines.append(f"- 截止：{t['due_date']}")
            return "\n".join(lines)

        if tool_name in ("send_email_internal", "send_email_external"):
            mid = output.get("message_id", "")
            n = output.get("recipients", "")
            kind = "内部邮件" if tool_name == "send_email_internal" else "外部邮件"
            return f"{kind}已发送(编号 `{mid}`，收件人 {n} 人)。"

        if tool_name == "create_ticket":
            t = output.get("ticket") or {}
            if not t:
                return "工单已创建。"
            lines = [f"工单已创建：**{t.get('title', '')}**(单号 `{t.get('ticket_id', '')}`)"]
            lines.append(
                f"- 客户：{t.get('customer_id', '')} · 优先级：{t.get('priority', '')} · 状态：{t.get('status', '')}"
            )
            return "\n".join(lines)

        if tool_name == "update_ticket":
            t = output.get("ticket") or {}
            if not t:
                return "工单已更新。"
            updated = output.get("updated_fields") or []
            comments = t.get("comments") or []
            last_note = comments[-1].get("text") if comments else ""
            return (
                f"工单 `{t.get('ticket_id', '')}` 已更新：状态 **{t.get('status', '')}**"
                + (f"(变更字段：{', '.join(updated)})" if updated else "")
                + (f"，备注：{last_note}" if last_note else "")
            )

        if tool_name == "query_my_approvals":
            items = output.get("approvals") or []
            if not items:
                return "你目前没有发起过审批单。高风险操作(如发外部邮件)提交后会生成审批单，进度可在这里查看。"
            lines = [f"你发起的审批单共 **{output.get('total', len(items))}** 条，最近 {len(items)} 条："]
            for a in items:
                line = f"- `{a.get('approval_id', '')}` {a.get('summary') or a.get('operation_type', '')}:**{a.get('status_label') or a.get('status', '')}**"
                if a.get("approver_id"):
                    line += f"(审批人 {a['approver_id']})"
                lines.append(line)
            return "\n".join(lines)

        # 兜底:键值对平铺,不直接暴露原始 dict 字符串
        pairs = [f"- {k}:{v}" for k, v in list(output.items())[:8]]
        return "执行结果：\n" + "\n".join(pairs)

    @classmethod
    def _format_answer(cls, plans: list[ToolCallPlan], result) -> str:
        """格式化最终回答"""
        if result.success:
            if len(plans) == 1:
                output = getattr(result, "output", {}) or getattr(result, "outputs", {})
                return cls._fmt_tool_output(plans[0].tool, output)

            # 多工具
            outputs = getattr(result, "outputs", {})
            parts = []
            for i, plan in enumerate(plans, start=1):
                step_output = outputs.get(f"step{i}", {})
                parts.append(cls._fmt_tool_output(plan.tool, step_output))
            return "\n\n".join(parts)

        # 失败
        if getattr(result, "compensated", False):
            errors = getattr(result, "compensation_errors", [])
            if errors:
                return (
                    f"工具执行失败，已自动补偿回滚。"
                    f"但有 {len(errors)} 个补偿失败需运维介入： {errors}"
                )
            return "工具执行失败，已自动补偿回滚所有已执行步骤。"

        return f"工具执行失败： {getattr(result, 'error', '未知错误')}"
