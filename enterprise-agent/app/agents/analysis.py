"""AnalysisAgent:数据分析 Agent(W6 完整实现)

职责：
- 业务数据统计分析(订单金额、订单数、客户销售额等)
- 对比 / 趋势 / 排名类问题，输出中文分析报告
- 严格的 RBAC:数据分析需要 query_order 权限，客户维度需 query_customer

两跳 + 多跳流程(控制 LLM 成本):
1. [lite 云端轻量] 查询解析：把用户问题解析成分析计划 JSON
   (metrics/entities/compare/dimensions)，失败降级为全实体 + 默认指标
2. [Python 本地计算] 对 Mock 数据做真实聚合(分组求和/计数/对比)，不调 LLM
3. [primary 云端大模型] 报告生成：基于计算结果写中文分析报告，
   允许其请求一次补充数据(多跳，最多 2 轮后强制输出),
   prompt 明确约束"只能使用给定数据，禁止编造数字"
4. LLM 整体失败降级：直接返回 Markdown 表格化的计算结果

模型分层理由：
- 查询解析是结构化抽取任务，用轻量模型足够且成本低
- 数值计算交给 Python 保证准确(LLM 不擅长算术，也避免幻觉数字)
- 报告撰写需要语言能力，用大模型保证质量
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from loguru import logger

from app.agents.knowledge import AgentResult
from app.rag.llm import get_lite_llm, get_primary_llm
from app.security.rbac import ROLE_TOOLS, AgentRole
from app.tools.crm import get_all_customers, get_all_orders


# Prompt 统一从注册表获取(P2-1:版本管理/A/B;代码默认值见 app/prompts/defaults.py)
from app.prompts import get_prompt
from app.prompts.defaults import ANALYSIS_REPORT_HOP_NOTE


# 默认分析计划(解析失败时降级用)
_DEFAULT_METRICS = ["order_amount", "order_count", "revenue"]
# 多跳补充数据最大轮数
_MAX_DATA_ROUNDS = 2


class AnalysisAgent:
    """数据分析 Agent(W6 完整实现)

    构造签名与 executor.py 的调用约定保持一致：
    AnalysisAgent(user_role=role, user_dept=dept) → await agent.run(query)
    """

    def __init__(self, user_role: AgentRole, user_dept: Optional[str] = None):
        self.user_role = user_role
        self.user_dept = user_dept
        allowed = ROLE_TOOLS.get(user_role, [])
        # 数据分析核心权限:订单数据
        self._can_query_order = "query_order" in allowed
        # 客户维度权限(客户名称/等级/累计销售额)
        self._can_query_customer = "query_customer" in allowed

    async def run(self, query: str) -> AgentResult:
        """执行数据分析：RBAC 校验 → 计划解析 → Python 计算 → LLM 报告"""
        start = time.time()
        logger.info(
            f"AnalysisAgent 开始： role={self.user_role.value}, "
            f"dept={self.user_dept}, query={query[:80]!r}"
        )

        # 1. RBAC 校验:无 query_order 权限直接拒绝
        if not self._can_query_order:
            latency_ms = int((time.time() - start) * 1000)
            logger.warning(
                f"AnalysisAgent RBAC 拒绝： role={self.user_role.value} 无 query_order 权限"
            )
            return AgentResult(
                agent_name="analysis",
                success=False,
                confidence=0.0,
                output={
                    "answer": (
                        f"抱歉，您的角色({self.user_role.value})没有订单数据查询权限，"
                        "无法进行数据分析。如需分析支持，请联系销售或财务同事协助。"
                    ),
                    "coverage": "none",
                    "stage": "rbac_denied",
                },
                sources=[],
                error="rbac_denied: no query_order permission",
                latency_ms=latency_ms,
                needs_replan=False,
            )

        # 2. 取数(RBAC 决定可取哪些维度)
        orders = get_all_orders()
        customers = get_all_customers() if self._can_query_customer else []
        customer_ids = [c["customer_id"] for c in get_all_customers()]  # 实体全集(仅 ID)

        # 3. 第 1 跳:lite LLM 解析分析计划(失败降级默认计划)
        plan = await self._parse_plan(query, customer_ids)
        logger.info(f"AnalysisAgent 分析计划： {plan}")

        # 4. Python 真实聚合计算(不调 LLM)
        computed = self._compute(plan, orders, customers)

        # 5. 多跳报告生成:primary LLM 可请求一次补充数据,最多 2 轮
        answer = await self._generate_report(query, computed, plan, orders, customers)

        latency_ms = int((time.time() - start) * 1000)
        has_data = bool(computed.get("per_entity"))
        logger.info(
            f"AnalysisAgent 完成： entities={len(computed.get('per_entity', {}))}, "
            f"latency={latency_ms}ms"
        )

        return AgentResult(
            agent_name="analysis",
            success=has_data,
            confidence=0.8 if has_data else 0.3,
            output={
                "answer": answer,
                "data": computed,
                "coverage": "full" if has_data else "none",
                "stage": "analysis_complete",
            },
            sources=[],
            latency_ms=latency_ms,
            needs_replan=not has_data,
            replan_reason=None if has_data else "无可分析数据",
        )

    # ============ 内部方法 ============

    async def _parse_plan(self, query: str, entity_ids: list[str]) -> dict:
        """第 1 跳：用 lite LLM 把 query 解析成分析计划 JSON

        解析失败时降级：全部实体 + 默认指标 + 按是否含对比关键词判断 compare。
        """
        default_plan = {
            "metrics": list(_DEFAULT_METRICS),
            "entities": list(entity_ids),
            "compare": any(kw in query for kw in ["对比", "比较", "排名", "vs"]),
            "dimensions": ["customer"],
        }
        try:
            from app.graph.planner import _parse_llm_json  # 复用容错 JSON 解析

            llm = get_lite_llm()
            tpl, pv = get_prompt("analysis_plan_parse")
            logger.debug(f"prompt=analysis_plan_parse v{pv}")
            prompt = tpl.format(
                entities=", ".join(entity_ids), query=query
            )
            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = resp.content if hasattr(resp, "content") else str(resp)
            logger.debug(f"AnalysisAgent 计划解析响应： {raw[:300]}")

            parsed = _parse_llm_json(raw)
            if not parsed:
                logger.warning("AnalysisAgent 计划解析失败，降级默认计划")
                return default_plan

            # 校验并清洗:实体只保留存在的,指标只保留合法的
            entities = [e for e in parsed.get("entities", []) if e in entity_ids]
            metrics = [m for m in parsed.get("metrics", []) if m in _DEFAULT_METRICS]
            return {
                "metrics": metrics or default_plan["metrics"],
                "entities": entities or default_plan["entities"],
                "compare": bool(parsed.get("compare", default_plan["compare"])),
                "dimensions": parsed.get("dimensions") or ["customer"],
            }
        except Exception as e:  # noqa: BLE001
            logger.warning(f"AnalysisAgent 计划解析 LLM 失败，降级默认计划： {e}")
            return default_plan

    def _compute(
        self, plan: dict, orders: list[dict], customers: list[dict]
    ) -> dict:
        """Python 本地聚合计算(不调 LLM，保证数字准确)

        按客户分组：订单金额求和、订单数计数、累计销售额；
        compare=True 时额外计算两两差值与比例。
        """
        entities: list[str] = plan.get("entities", [])
        metrics: list[str] = plan.get("metrics", _DEFAULT_METRICS)
        customer_map = {c["customer_id"]: c for c in customers}

        per_entity: dict[str, dict[str, Any]] = {}
        for cid in entities:
            ent_orders = [o for o in orders if o.get("customer_id") == cid]
            row: dict[str, Any] = {"customer_id": cid}
            customer = customer_map.get(cid)
            if customer:
                row["name"] = customer.get("name")
                row["level"] = customer.get("level")
            if "order_amount" in metrics:
                row["order_amount"] = round(
                    sum(float(o.get("amount", 0)) for o in ent_orders), 2
                )
            if "order_count" in metrics:
                row["order_count"] = len(ent_orders)
            if "revenue" in metrics:
                # revenue 来自客户档案;无客户权限时用订单金额近似
                row["revenue"] = (
                    float(customer.get("total_revenue", 0))
                    if customer
                    else row.get("order_amount", 0.0)
                )
            row["order_ids"] = [o["order_id"] for o in ent_orders]
            per_entity[cid] = row

        result: dict[str, Any] = {
            "metrics": metrics,
            "dimensions": plan.get("dimensions", ["customer"]),
            "per_entity": per_entity,
            "totals": {
                "order_amount": round(
                    sum(r.get("order_amount", 0) for r in per_entity.values()), 2
                ),
                "order_count": sum(r.get("order_count", 0) for r in per_entity.values()),
            },
        }

        # 对比分析:两两差值与比例(按订单金额)
        if plan.get("compare") and len(per_entity) >= 2:
            comparisons = []
            ids = list(per_entity.keys())
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = per_entity[ids[i]], per_entity[ids[j]]
                    amt_a = a.get("order_amount", 0)
                    amt_b = b.get("order_amount", 0)
                    comparisons.append(
                        {
                            "a": ids[i],
                            "b": ids[j],
                            "metric": "order_amount",
                            "a_value": amt_a,
                            "b_value": amt_b,
                            "diff": round(amt_a - amt_b, 2),
                            "ratio": round(amt_a / amt_b, 2) if amt_b else None,
                        }
                    )
            result["comparisons"] = comparisons

        return result

    async def _generate_report(
        self,
        query: str,
        computed: dict,
        plan: dict,
        orders: list[dict],
        customers: list[dict],
    ) -> str:
        """多跳报告生成：primary LLM 基于计算结果写报告

        - LLM 可输出 {"need_more": {"entities": [...]}} 请求一次补充数据，
          补充后重新计算，最多 _MAX_DATA_ROUNDS 轮后强制输出报告
        - LLM 整体失败时降级：返回 Markdown 表格化的计算结果
        """
        try:
            llm = get_primary_llm()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"AnalysisAgent 主 LLM 初始化失败，降级表格输出： {e}")
            return self._fallback_table(computed)

        current = computed
        current_plan = plan
        for round_no in range(1, _MAX_DATA_ROUNDS + 2):  # 最后一轮强制输出
            # P2-1:模板含 {hop_note} 占位,强制轮传提示(原为运行时字符串拼接)
            tpl, pv = get_prompt("analysis_report")
            hop_note = (
                ANALYSIS_REPORT_HOP_NOTE if round_no > _MAX_DATA_ROUNDS else ""
            )
            logger.debug(f"prompt=analysis_report v{pv}, round={round_no}")
            prompt = tpl.format(
                query=query,
                computed=json.dumps(current, ensure_ascii=False, indent=2),
                hop_note=hop_note,
            )
            try:
                resp = await llm.ainvoke(
                    [HumanMessage(content=prompt)],
                    config={"tags": ["final_answer"]},  # 流式输出标记
                )
                raw = resp.content if hasattr(resp, "content") else str(resp)
                raw = raw.strip()
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"AnalysisAgent 报告生成第 {round_no} 轮 LLM 失败，降级表格输出： {e}"
                )
                return self._fallback_table(current)

            # 多跳:解析是否请求补充数据
            need_more = self._parse_need_more(raw)
            # JSON 变体(格式破损但明显是 need_more 协议输出)也按协议处理,
            # 否则会把协议 JSON 当报告抛给用户
            is_protocol = need_more is not None or (
                raw.lstrip().startswith("{") and '"need_more"' in raw
            )
            if is_protocol and round_no <= _MAX_DATA_ROUNDS:
                extra = [
                    e
                    for e in (need_more or {}).get("entities", [])
                    if e not in current_plan.get("entities", [])
                ]
                known_ids = {c["customer_id"] for c in get_all_customers()}
                extra = [e for e in extra if e in known_ids]
                if extra:
                    logger.info(
                        f"AnalysisAgent 多跳第 {round_no} 轮：补充实体 {extra}, "
                        f"原因： {(need_more or {}).get('reason', '')[:60]}"
                    )
                    current_plan = {
                        **current_plan,
                        "entities": current_plan.get("entities", []) + extra,
                    }
                    current = self._compute(current_plan, orders, customers)
                    continue
                logger.info(
                    f"AnalysisAgent 多跳请求的实体均已覆盖或不存在，进入下一轮输出"
                )
                continue

            if not raw:
                logger.warning("AnalysisAgent 报告为空，降级表格输出")
                return self._fallback_table(current)
            if is_protocol:
                # 强制轮仍输出 need_more 协议 JSON,降级为表格而不是把 JSON 抛给用户
                logger.warning("AnalysisAgent 强制轮仍请求补充数据，降级表格输出")
                return self._fallback_table(current)
            return raw

        return self._fallback_table(current)

    @staticmethod
    def _parse_need_more(raw: str) -> Optional[dict]:
        """解析 LLM 是否请求补充数据(返回 need_more 部分，否则 None)"""
        from app.graph.planner import _parse_llm_json

        parsed = _parse_llm_json(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("need_more"), dict):
            return parsed["need_more"]
        return None

    @staticmethod
    def _fallback_table(computed: dict) -> str:
        """降级输出：把计算结果渲染成 Markdown 表格(不依赖 LLM)"""
        per_entity = computed.get("per_entity", {})
        if not per_entity:
            return "暂无可分析的数据。"

        lines = [
            "| 客户ID | 客户名称 | 订单金额 | 订单数 | 累计销售额 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for cid, row in per_entity.items():
            lines.append(
                f"| {cid} | {row.get('name') or '-'} "
                f"| {row.get('order_amount', 0):,.2f} "
                f"| {row.get('order_count', 0)} "
                f"| {row.get('revenue', 0):,.2f} |"
            )
        totals = computed.get("totals", {})
        lines.append(
            f"\n合计：订单金额 {totals.get('order_amount', 0):,.2f},"
            f"订单数 {totals.get('order_count', 0)}。"
        )
        for comp in computed.get("comparisons", []):
            ratio = f"，比例为 {comp['ratio']}" if comp.get("ratio") else ""
            lines.append(
                f"对比：{comp['a']} 比 {comp['b']} 订单金额"
                f"{'多' if comp['diff'] >= 0 else '少'} {abs(comp['diff']):,.2f}{ratio}。"
            )
        return "\n".join(lines)
