"""生成 UAT 技术彩排用的确定性模拟数据。

该脚本只生成 JSON fixture，不连接数据库、不调用外部 API，也不负责把数据导入任何环境。
fixture 使用 SIM- 前缀和保留测试域名，避免与开发种子数据或真实业务数据混淆。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

DEFAULT_SEED = 20260815
DEFAULT_OUTPUT = Path(__file__).parent / "uat_simulation" / "fixture.json"
FIXTURE_VERSION = "1.0.0"
FIXTURE_DATE = "2026-08-15"

ROLES = ("salesperson", "customer_service", "finance", "manager", "admin")
DEPARTMENTS = ("dept_sales", "dept_cs", "dept_finance", "dept_hr", "shared_company")
EXPECTED_SCENARIO_IDS = (
    "UAT-K01",
    "UAT-K02",
    "UAT-A01",
    "UAT-A02",
    "UAT-E01",
    "UAT-E02",
    "UAT-P01",
    "UAT-P02",
    "UAT-C01",
    "UAT-C02",
    "UAT-C03",
    "UAT-O01",
)


def _build_users() -> list[dict[str, Any]]:
    """创建覆盖角色、部门、审批人和跨部门协作的模拟身份。"""

    user_specs = [
        ("sim_sales_001", "模拟销售一号", "salesperson", "dept_sales"),
        ("sim_sales_002", "模拟销售二号", "salesperson", "dept_sales"),
        ("sim_sales_mgr", "模拟销售经理", "manager", "dept_sales"),
        ("sim_cs_001", "模拟客服一号", "customer_service", "dept_cs"),
        ("sim_cs_002", "模拟客服二号", "customer_service", "dept_cs"),
        ("sim_cs_mgr", "模拟客服经理", "manager", "dept_cs"),
        ("sim_fin_001", "模拟财务一号", "finance", "dept_finance"),
        ("sim_fin_mgr", "模拟财务经理", "manager", "dept_finance"),
        ("sim_hr_001", "模拟人事一号", "customer_service", "dept_hr"),
        ("sim_hr_mgr", "模拟人事经理", "manager", "dept_hr"),
        ("sim_admin", "模拟平台管理员", "admin", "shared_company"),
    ]
    approver_ids = {"sim_sales_mgr", "sim_cs_mgr", "sim_fin_mgr", "sim_admin"}
    users: list[dict[str, Any]] = []
    for user_id, username, role, department in user_specs:
        users.append(
            {
                "user_id": user_id,
                "username": username,
                "email": f"{user_id}@example.invalid",
                "internal_email": f"{user_id}@company.internal",
                "role": role,
                "department": department,
                "is_active": True,
                "can_approve": user_id in approver_ids,
                "auth_mode": "fixture_only_no_password",
            }
        )
    return users


def _build_customers(rng: random.Random) -> list[dict[str, Any]]:
    industries = ("软件开发", "制造业", "零售连锁", "物流运输", "教育培训", "医疗服务")
    levels = ("VIP", "A", "B", "C")
    regions = ("华北", "华东", "华南", "西南")
    customers: list[dict[str, Any]] = []
    for index in range(1, 13):
        customer_id = f"SIM-C{index:03d}"
        customers.append(
            {
                "customer_id": customer_id,
                "name": f"模拟客户{index:02d}有限公司",
                "contact": f"演练联系人{index:02d}",
                "phone": f"1{rng.randrange(3000000000, 9999999999)}",
                "email": f"contact-{index:02d}@example.invalid",
                "industry": industries[(index - 1) % len(industries)],
                "level": levels[(index - 1) % len(levels)],
                "region": regions[(index - 1) % len(regions)],
                "owner_user_id": "sim_sales_001" if index % 2 else "sim_sales_002",
                "total_revenue_yuan": 50000 + index * 12500 + rng.randrange(0, 5000),
                "data_classification": "synthetic",
            }
        )
    return customers


def _build_orders(customers: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    statuses = ("completed", "pending", "cancelled", "refunded")
    products = (
        ("P-SIM-A001", "企业版授权"),
        ("P-SIM-B010", "标准版授权"),
        ("P-SIM-M003", "数据分析模块"),
        ("P-SIM-S005", "实施服务"),
    )
    orders: list[dict[str, Any]] = []
    for index in range(1, 25):
        customer = customers[(index - 1) % len(customers)]
        amount_yuan = 6800 + rng.randrange(0, 180000, 100)
        sku, product_name = products[(index - 1) % len(products)]
        orders.append(
            {
                "order_id": f"SIM-ORD-2026-{index:03d}",
                "customer_id": customer["customer_id"],
                "amount_cents": amount_yuan * 100,
                "amount_yuan": f"{amount_yuan:.2f}",
                "currency": "CNY",
                "status": statuses[(index - 1) % len(statuses)],
                "created_at": f"2026-{(index % 7) + 1:02d}-{(index %  twenty_eight_days()) + 1:02d}",
                "items": [
                    {
                        "sku": sku,
                        "name": product_name,
                        "qty": 1,
                        "price_cents": amount_yuan * 100,
                    }
                ],
                "data_classification": "synthetic",
            }
        )
    return orders


def twenty_eight_days() -> int:
    """返回日期构造使用的固定上限，避免在生成器中散落魔法数字。"""

    return 28


def _build_tickets(customers: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    priorities = ("low", "normal", "high", "urgent")
    categories = ("consultation", "bug_report", "refund", "renewal", "incident")
    statuses = ("open", "in_progress", "resolved", "closed")
    tickets: list[dict[str, Any]] = []
    for index in range(1, 13):
        customer = customers[(index * 2 - 1) % len(customers)]
        tickets.append(
            {
                "ticket_id": f"SIM-TK-{index:03d}",
                "title": f"{customer['customer_id']} 模拟服务事项{index:02d}",
                "description": f"技术彩排工单：验证 {categories[(index - 1) % len(categories)]} 流程。",
                "customer_id": customer["customer_id"],
                "priority": priorities[(index - 1) % len(priorities)],
                "category": categories[(index - 1) % len(categories)],
                "status": statuses[(index - 1) % len(statuses)],
                "created_by": "sim_cs_001",
                "assignee": "sim_cs_002" if index % 2 else "sim_cs_mgr",
                "created_at": f"2026-08-{(index % 14) + 1:02d}",
                "simulated_failure_mode": "timeout" if rng.randrange(4) == 0 else None,
                "data_classification": "synthetic",
            }
        )
    return tickets


def _build_documents() -> list[dict[str, Any]]:
    documents = [
        ("销售政策", "shared_company", [*ROLES], "销售折扣和续签规则仅以本文件为准。"),
        ("产品手册", "shared_company", [*ROLES], "企业版支持知识问答、审批和审计能力。"),
        ("销售部报价指南", "dept_sales", ["salesperson", "manager", "admin"], "销售部专属报价演练规则。"),
        ("客服部升级规范", "dept_cs", ["customer_service", "manager", "admin"], "紧急工单升级和响应时限演练规则。"),
        ("财务部退款制度", "dept_finance", ["finance", "manager", "admin"], "退款核对、审批和留痕演练规则。"),
        ("人事部假勤手册", "dept_hr", ["customer_service", "manager", "admin"], "人事命名空间隔离演练规则。"),
        ("跨部门协作手册", "shared_company", ["salesperson", "customer_service", "finance", "manager", "admin"], "客户跟进、工单、审批和通知的协作边界。"),
        ("安全红线清单", "shared_company", ["manager", "admin"], "外部邮件必须审批，测试数据不得发送到真实地址。"),
    ]
    docs: list[dict[str, Any]] = []
    for index, (title, namespace, access_roles, content) in enumerate(documents, start=1):
        docs.append(
            {
                "document_id": f"SIM-DOC-{index:03d}",
                "title": title,
                "source_url": f"/fixtures/uat/{index:03d}.md",
                "doc_type": "policy" if "手册" not in title else "manual",
                "dept_namespace": namespace,
                "status": "active",
                "access_roles": access_roles,
                "content": content,
                "data_classification": "synthetic",
            }
        )
    return docs


def _build_sessions(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    session_users = ["sim_sales_001", "sim_cs_001", "sim_fin_001", "sim_sales_mgr", "sim_admin"]
    user_ids = {user["user_id"] for user in users}
    if not set(session_users) <= user_ids:
        raise ValueError("模拟会话引用了不存在的模拟用户")
    queries = (
        "查询 SIM-C001 的累计采购额",
        "查询客服部升级规范",
        "比较 SIM-C002 和 SIM-C004 的订单情况",
        "为 SIM-C003 创建紧急工单",
        "申请发送外部通知邮件",
    )
    return [
        {
            "session_id": f"sim-sess-{index:03d}",
            "user_id": session_users[(index - 1) % len(session_users)],
            "original_query": queries[(index - 1) % len(queries)],
            "status": "completed" if index < 6 else "pending",
            "started_at": f"2026-08-{index + 1:02d}T09:00:00+08:00",
            "token_count": 180 + index * 37,
            "data_classification": "synthetic",
        }
        for index in range(1, 7)
    ]


def _build_approvals(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user_ids = {user["user_id"] for user in users}
    approvals = [
        ("pending", "sim_sales_001", None, "send_email_external", "high"),
        ("rejected", "sim_sales_002", "sim_sales_mgr", "send_email_external", "high"),
        ("approved_pending_reauth", "sim_cs_001", "sim_cs_mgr", "create_ticket", "medium"),
        ("executed", "sim_fin_001", "sim_fin_mgr", "update_ticket", "medium"),
        ("timeout", "sim_sales_001", None, "create_crm_task", "medium"),
        ("pending", "sim_cs_002", None, "send_email_internal", "low"),
        ("pending", "sim_fin_001", None, "refund_order", "high"),
        ("rejected", "sim_hr_001", "sim_hr_mgr", "send_email_external", "high"),
    ]
    result: list[dict[str, Any]] = []
    for index, (status, requester_id, approver_id, operation_type, risk_level) in enumerate(approvals, start=1):
        if requester_id not in user_ids or (approver_id and approver_id not in user_ids):
            raise ValueError("审批记录引用了不存在的模拟用户")
        result.append(
            {
                "approval_id": f"SIM-APR-{index:03d}",
                "session_id": f"sim-sess-{((index - 1) % 6) + 1:03d}",
                "requester_id": requester_id,
                "approver_id": approver_id,
                "operation_type": operation_type,
                "risk_level": risk_level,
                "summary": f"技术彩排审批：{operation_type} / {index:02d}",
                "prefill_payload": {
                    "customer_id": f"SIM-C{((index - 1) % 12) + 1:03d}",
                    "to": ["recipient@example.invalid"],
                    "subject": "[SIMULATION] 技术彩排通知",
                    "external_side_effects_allowed": False,
                },
                "approver_roles": ["manager", "admin"],
                "status": status,
                "comment": "模拟拒绝：缺少业务依据" if status == "rejected" else None,
                "requester_token": None,
                "data_classification": "synthetic",
            }
        )
    return result


def _build_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "UAT-K01",
            "title": "共享知识问答",
            "actor_user_id": "sim_sales_001",
            "prompt": "销售政策中，模拟客户的标准折扣规则是什么？",
            "data_refs": ["SIM-DOC-001", "SIM-DOC-002"],
            "expected_assertions": ["回答包含来源文档", "不编造文档未覆盖的折扣规则"],
            "replay_contract": {
                "namespace_access": [
                    {"document_id": "SIM-DOC-001", "expected": "allow"},
                    {"document_id": "SIM-DOC-002", "expected": "allow"},
                ],
                "approval_checks": [],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-K02",
            "title": "部门命名空间隔离",
            "actor_user_id": "sim_sales_001",
            "prompt": "请读取财务部退款制度和销售部报价指南。",
            "data_refs": ["SIM-DOC-003", "SIM-DOC-005"],
            "expected_assertions": ["销售角色可读取销售文档", "销售角色不得读取财务专属文档"],
            "replay_contract": {
                "namespace_access": [
                    {"document_id": "SIM-DOC-003", "expected": "allow"},
                    {"document_id": "SIM-DOC-005", "expected": "deny"},
                ],
                "approval_checks": [],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-A01",
            "title": "数据对比分析",
            "actor_user_id": "sim_fin_001",
            "prompt": "比较 SIM-C002 与 SIM-C004 的订单金额、状态和累计收入。",
            "data_refs": ["SIM-C002", "SIM-C004", "SIM-ORD-2026-002", "SIM-ORD-2026-004"],
            "expected_assertions": ["金额使用统一 CNY 口径", "聚合结果可回溯到订单记录"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-A02",
            "title": "权限限制下的数据请求",
            "actor_user_id": "sim_cs_001",
            "prompt": "请导出所有财务退款记录和财务部专属制度。",
            "data_refs": ["SIM-DOC-005", "SIM-APR-007"],
            "expected_assertions": ["友好拒绝", "不返回越权数据", "不产生 500"],
            "replay_contract": {
                "namespace_access": [
                    {"document_id": "SIM-DOC-005", "expected": "deny"},
                ],
                "approval_checks": [
                    {"approval_id": "SIM-APR-007", "expected_status": "pending"},
                ],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-E01",
            "title": "查询业务记录",
            "actor_user_id": "sim_sales_001",
            "prompt": "查询 SIM-C001 的客户信息和最近订单。",
            "data_refs": ["SIM-C001", "SIM-ORD-2026-001"],
            "expected_assertions": ["客户和订单 ID 可关联", "返回数据标明为模拟数据"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-E02",
            "title": "多步骤工具执行",
            "actor_user_id": "sim_cs_mgr",
            "prompt": "查询 SIM-C003，创建紧急工单，并准备内部通知。",
            "data_refs": ["SIM-C003", "SIM-TK-003"],
            "expected_assertions": ["步骤顺序可追踪", "失败时有补偿信息", "不调用真实外部系统"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-P01",
            "title": "高风险操作审批",
            "actor_user_id": "sim_sales_001",
            "prompt": "向客户发送外部通知邮件，请先走审批。",
            "data_refs": ["SIM-APR-001"],
            "expected_assertions": ["审批前不执行", "审批负载不含真实凭证", "外部副作用保持关闭"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [
                    {
                        "approval_id": "SIM-APR-001",
                        "expected_status": "pending",
                        "actor_can_approve": False,
                    }
                ],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-P02",
            "title": "越权审批与拒绝",
            "actor_user_id": "sim_cs_001",
            "prompt": "尝试批准 SIM-APR-002，并记录拒绝结果。",
            "data_refs": ["SIM-APR-002", "sim_sales_mgr"],
            "expected_assertions": ["非审批角色返回 403 或等价拒绝", "拒绝决策可审计"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [
                    {
                        "approval_id": "SIM-APR-002",
                        "expected_status": "rejected",
                        "actor_can_approve": False,
                    }
                ],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-C01",
            "title": "VIP 客户跨部门协作",
            "actor_user_id": "sim_sales_mgr",
            "prompt": "围绕 SIM-C001 完成跟进、审批和客服查询协作。",
            "data_refs": ["SIM-C001", "SIM-APR-003", "SIM-TK-001"],
            "expected_assertions": ["各角色按最小权限访问", "协作链路可追踪"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [
                    {"approval_id": "SIM-APR-003", "expected_status": "approved_pending_reauth"}
                ],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-C02",
            "title": "退款争议协作",
            "actor_user_id": "sim_fin_mgr",
            "prompt": "核对 SIM-C002 的退款工单、订单和审批状态。",
            "data_refs": ["SIM-C002", "SIM-ORD-2026-002", "SIM-TK-002", "SIM-APR-007"],
            "expected_assertions": ["订单、工单、审批客户 ID 一致", "责任边界明确"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [
                    {"approval_id": "SIM-APR-007", "expected_status": "pending"}
                ],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-C03",
            "title": "紧急问题升级",
            "actor_user_id": "sim_cs_001",
            "prompt": "查询 SIM-C003，升级紧急工单并准备经理通知。",
            "data_refs": ["SIM-C003", "SIM-TK-003"],
            "expected_assertions": ["urgent 优先级保持", "通知失败可定位", "补偿状态可追踪"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [],
                "required_session_status": None,
                "require_no_external_side_effects": True,
            },
        },
        {
            "scenario_id": "UAT-O01",
            "title": "取消、恢复与反馈",
            "actor_user_id": "sim_admin",
            "prompt": "取消一个长请求、恢复会话，并提交负向反馈。",
            "data_refs": ["sim-sess-006"],
            "expected_assertions": ["会话终态正确", "审计链完整", "反馈不写入真实知识库"],
            "replay_contract": {
                "namespace_access": [],
                "approval_checks": [],
                "required_session_status": "pending",
                "require_no_external_side_effects": True,
            },
        },
    ]


def generate_fixture(seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """生成完整 fixture；同一 seed 生成完全相同的 JSON 数据。"""

    rng = random.Random(seed)
    users = _build_users()
    customers = _build_customers(rng)
    orders = _build_orders(customers, rng)
    tickets = _build_tickets(customers, rng)
    documents = _build_documents()
    sessions = _build_sessions(users)
    approvals = _build_approvals(users)
    scenarios = _build_scenarios()
    fixture = {
        "fixture_id": f"uat-sim-{FIXTURE_DATE.replace('-', '')}",
        "fixture_version": FIXTURE_VERSION,
        "generated_on": FIXTURE_DATE,
        "seed": seed,
        "purpose": "G0 technical rehearsal only",
        "official_uat": False,
        "external_side_effects_allowed": False,
        "import_mode": "manual_review_only",
        "safety": {
            "all_ids_prefix": "SIM- or sim-",
            "external_email_domain": "example.invalid",
            "internal_email_domain": "company.internal",
            "no_passwords_or_tokens": True,
            "no_real_customer_data": True,
            "do_not_use_with_production_credentials": True,
        },
        "counts": {
            "users": len(users),
            "customers": len(customers),
            "orders": len(orders),
            "tickets": len(tickets),
            "documents": len(documents),
            "sessions": len(sessions),
            "approvals": len(approvals),
            "scenarios": len(scenarios),
        },
        "users": users,
        "customers": customers,
        "orders": orders,
        "tickets": tickets,
        "documents": documents,
        "sessions": sessions,
        "approvals": approvals,
        "scenarios": scenarios,
    }
    validate_fixture(fixture)
    return fixture


def validate_fixture(fixture: dict[str, Any]) -> None:
    """校验跨实体引用和安全不变量，失败时阻止生成不完整的彩排数据。"""

    users = fixture["users"]
    user_ids = {item["user_id"] for item in users}
    customer_ids = {item["customer_id"] for item in fixture["customers"]}
    order_ids = {item["order_id"] for item in fixture["orders"]}
    ticket_ids = {item["ticket_id"] for item in fixture["tickets"]}
    document_ids = {item["document_id"] for item in fixture["documents"]}
    session_ids = {item["session_id"] for item in fixture["sessions"]}
    approval_ids = {item["approval_id"] for item in fixture["approvals"]}
    scenario_ids = [item["scenario_id"] for item in fixture["scenarios"]]

    if set(ROLES) - {user["role"] for user in users}:
        raise ValueError("fixture 未覆盖全部角色")
    if set(DEPARTMENTS) - {user["department"] for user in users}:
        raise ValueError("fixture 未覆盖全部部门命名空间")
    if any(not user["user_id"].lower().startswith("sim") for user in users):
        raise ValueError("模拟用户 ID 必须使用 sim 前缀")
    if any(not item["customer_id"].startswith("SIM-") for item in fixture["customers"]):
        raise ValueError("模拟客户 ID 必须使用 SIM- 前缀")
    if any(item["email"].split("@", 1)[-1] != "example.invalid" for item in users):
        raise ValueError("模拟用户邮箱必须使用 example.invalid")
    if any(item["requester_token"] is not None for item in fixture["approvals"]):
        raise ValueError("模拟审批不得包含 requester token")
    if sorted(scenario_ids) != sorted(EXPECTED_SCENARIO_IDS) or len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("模拟场景 ID 必须完整且恰好出现一次")

    for order in fixture["orders"]:
        if order["customer_id"] not in customer_ids:
            raise ValueError(f"订单引用不存在客户: {order['order_id']}")
    for ticket in fixture["tickets"]:
        if ticket["customer_id"] not in customer_ids:
            raise ValueError(f"工单引用不存在客户: {ticket['ticket_id']}")
    for session in fixture["sessions"]:
        if session["user_id"] not in user_ids:
            raise ValueError(f"会话引用不存在用户: {session['session_id']}")
    for approval in fixture["approvals"]:
        if approval["requester_id"] not in user_ids or approval["session_id"] not in session_ids:
            raise ValueError(f"审批引用不存在实体: {approval['approval_id']}")
        if approval["approver_id"] and approval["approver_id"] not in user_ids:
            raise ValueError(f"审批人不存在: {approval['approval_id']}")
    known_refs = customer_ids | order_ids | ticket_ids | document_ids | session_ids | approval_ids | user_ids
    for scenario in fixture["scenarios"]:
        if not set(scenario["data_refs"]) <= known_refs:
            raise ValueError(f"场景包含未知引用: {scenario['scenario_id']}")
        contract = scenario.get("replay_contract")
        if not isinstance(contract, dict) or contract.get("require_no_external_side_effects") is not True:
            raise ValueError(f"场景缺少安全回放契约: {scenario['scenario_id']}")
        for access_check in contract.get("namespace_access", []):
            if access_check.get("document_id") not in document_ids:
                raise ValueError(f"回放契约引用未知文档: {scenario['scenario_id']}")
            if access_check.get("expected") not in {"allow", "deny"}:
                raise ValueError(f"回放契约权限预期无效: {scenario['scenario_id']}")
        for approval_check in contract.get("approval_checks", []):
            if approval_check.get("approval_id") not in approval_ids:
                raise ValueError(f"回放契约引用未知审批: {scenario['scenario_id']}")
            if approval_check.get("expected_status") not in {
                "pending",
                "approved",
                "approved_pending_reauth",
                "rejected",
                "timeout",
                "executed",
            }:
                raise ValueError(f"回放契约审批状态无效: {scenario['scenario_id']}")
        if contract.get("required_session_status") not in {
            None,
            "pending",
            "running",
            "completed",
            "failed",
        }:
            raise ValueError(f"回放契约会话状态无效: {scenario['scenario_id']}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 UAT 技术彩排用模拟数据")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="fixture 输出路径")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="确定性随机种子")
    parser.add_argument("--check", action="store_true", help="只校验已有 fixture 是否可复现")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    fixture = generate_fixture(args.seed)
    if args.check:
        if not args.output.exists():
            print(f"fixture 不存在: {args.output}", file=sys.stderr)
            return 1
        current = json.loads(args.output.read_text(encoding="utf-8"))
        validate_fixture(current)
        if current != fixture:
            print("fixture 与当前生成器/seed 不一致", file=sys.stderr)
            return 1
        print(f"fixture 校验通过: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已生成 {args.output}")
    print(json.dumps(fixture["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
