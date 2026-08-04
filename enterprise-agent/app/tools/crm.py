"""CRM 工具(对接客户关系管理系统)

工具列表:
- query_customer: 查询客户信息(QUERY 类,无副作用)
- query_order: 查询订单信息(QUERY 类,无副作用)
- create_crm_task: 创建 CRM 跟进任务(ACTION 类,需 Saga 补偿)

W7 阶段用 Mock 实现,接口契约对应真实 CRM API:
- GET  /api/v1/customers/{customer_id}
- GET  /api/v1/orders/{order_id}
- POST /api/v1/crm_tasks

切换真实 API:覆盖 _call_external 方法,改用 httpx 调用 CRM_API_BASE
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolCategory, ToolResult


# ============ Schemas ============


class QueryCustomerSchema(BaseModel):
    """查询客户入参"""

    customer_id: str = Field(description="客户 ID,如 C001")
    fields: Optional[list[str]] = Field(
        default=None, description="指定返回字段,如 ['name','contact']"
    )


class QueryOrderSchema(BaseModel):
    """查询订单入参"""

    order_id: str = Field(description="订单 ID,如 ORD-2026-001")
    include_items: bool = Field(default=False, description="是否包含订单明细")


class CreateCrmTaskSchema(BaseModel):
    """创建 CRM 跟进任务入参"""

    customer_id: str = Field(description="关联客户 ID")
    title: str = Field(description="任务标题", max_length=200)
    description: str = Field(default="", description="任务描述", max_length=2000)
    # 本地小模型有时输出 assignee=null(不知填谁);允许为空,执行时默认填发起人
    assignee: Optional[str] = Field(default=None, description="负责人 user_id,不指定则为当前用户")
    due_date: Optional[str] = Field(default=None, description="截止日期 YYYY-MM-DD")
    priority: int = Field(default=1, ge=0, le=5, description="优先级 0-5")


# ============ Mock 数据 ============


_MOCK_CUSTOMERS = {
    "C001": {
        "customer_id": "C001",
        "name": "北京华信科技有限公司",
        "contact": "张经理",
        "phone": "010-88881234",
        "email": "zhang@huaxin-tech.com",
        "industry": "软件开发",
        "level": "VIP",
        "total_revenue": 2850000.00,
    },
    "C002": {
        "customer_id": "C002",
        "name": "上海瑞达贸易集团",
        "contact": "李总",
        "phone": "021-66668888",
        "email": "li@ruida-trade.com",
        "industry": "进出口贸易",
        "level": "A",
        "total_revenue": 1520000.00,
    },
    "C003": {
        "customer_id": "C003",
        "name": "深圳新创电子有限公司",
        "contact": "王工",
        "phone": "0755-22223333",
        "email": "wang@xinchuang-elec.com",
        "industry": "电子制造",
        "level": "B",
        "total_revenue": 680000.00,
    },
    "C004": {
        "customer_id": "C004",
        "name": "广州恒通物流股份",
        "contact": "陈总",
        "phone": "020-33334444",
        "email": "chen@hengtu-logistics.com",
        "industry": "物流运输",
        "level": "B",
        "total_revenue": 420000.00,
    },
    "C005": {
        "customer_id": "C005",
        "name": "杭州云图网络科技有限公司",
        "contact": "刘CTO",
        "phone": "0571-55556666",
        "email": "liu@yuntu-net.com",
        "industry": "互联网",
        "level": "A",
        "total_revenue": 1180000.00,
    },
    "C006": {
        "customer_id": "C006",
        "name": "成都天府制造有限公司",
        "contact": "赵厂长",
        "phone": "028-77778888",
        "email": "zhao@tianfu-mfg.com",
        "industry": "机械制造",
        "level": "C",
        "total_revenue": 85000.00,
    },
    "C007": {
        "customer_id": "C007",
        "name": "武汉中百零售集团",
        "contact": "孙总监",
        "phone": "027-99990000",
        "email": "sun@zhongbai-retail.com",
        "industry": "零售连锁",
        "level": "B",
        "total_revenue": 350000.00,
    },
    "C008": {
        "customer_id": "C008",
        "name": "南京博雅教育科技",
        "contact": "周校长",
        "phone": "025-11112222",
        "email": "zhou@boya-edu.com",
        "industry": "教育培训",
        "level": "C",
        "total_revenue": 52000.00,
    },
}

_MOCK_ORDERS = {
    "ORD-2026-001": {
        "order_id": "ORD-2026-001",
        "customer_id": "C001",
        "amount": 85000.00,
        "status": "completed",
        "created_at": "2026-01-15",
        "items": [
            {"sku": "P-A001", "name": "企业版授权(50人)", "qty": 1, "price": 80000},
            {"sku": "P-S005", "name": "实施服务", "qty": 1, "price": 5000},
        ],
    },
    "ORD-2026-002": {
        "order_id": "ORD-2026-002",
        "customer_id": "C002",
        "amount": 12000.00,
        "status": "pending",
        "created_at": "2026-07-20",
        "items": [{"sku": "P-B010", "name": "标准版授权(20人)", "qty": 1, "price": 12000}],
    },
    "ORD-2026-003": {
        "order_id": "ORD-2026-003",
        "customer_id": "C005",
        "amount": 156000.00,
        "status": "completed",
        "created_at": "2026-03-08",
        "items": [
            {"sku": "P-A001", "name": "企业版授权(100人)", "qty": 1, "price": 120000},
            {"sku": "P-S010", "name": "定制开发服务", "qty": 1, "price": 36000},
        ],
    },
    "ORD-2026-004": {
        "order_id": "ORD-2026-004",
        "customer_id": "C003",
        "amount": 6800.00,
        "status": "cancelled",
        "created_at": "2026-05-12",
        "items": [{"sku": "P-B010", "name": "标准版授权(20人)", "qty": 1, "price": 6800}],
    },
    "ORD-2026-005": {
        "order_id": "ORD-2026-005",
        "customer_id": "C001",
        "amount": 45000.00,
        "status": "pending",
        "created_at": "2026-07-22",
        "items": [
            {"sku": "P-M003", "name": "数据分析模块", "qty": 1, "price": 25000},
            {"sku": "P-M005", "name": "API接口扩展包", "qty": 1, "price": 20000},
        ],
    },
    "ORD-2026-006": {
        "order_id": "ORD-2026-006",
        "customer_id": "C007",
        "amount": 23000.00,
        "status": "completed",
        "created_at": "2026-06-10",
        "items": [
            {"sku": "P-B010", "name": "标准版授权(20人)", "qty": 1, "price": 12000},
            {"sku": "P-S003", "name": "现场培训服务", "qty": 1, "price": 11000},
        ],
    },
    "ORD-2026-007": {
        "order_id": "ORD-2026-007",
        "customer_id": "C004",
        "amount": 9500.00,
        "status": "pending",
        "created_at": "2026-07-25",
        "items": [{"sku": "P-S008", "name": "物流接口对接", "qty": 1, "price": 9500}],
    },
    "ORD-2026-008": {
        "order_id": "ORD-2026-008",
        "customer_id": "C002",
        "amount": 78000.00,
        "status": "refunded",
        "created_at": "2026-04-18",
        "items": [{"sku": "P-A001", "name": "企业版授权(50人)", "qty": 1, "price": 78000}],
    },
}

# Mock 创建的 CRM 任务存储(供补偿回滚用)
# 预置 2 个历史任务,让"查询已有任务"场景更真实
_mock_crm_tasks: dict[str, dict] = {
    "CT-EXIST001": {
        "task_id": "CT-EXIST001",
        "customer_id": "C001",
        "title": "Q2季度复盘沟通",
        "description": "与张经理回顾 Q2 使用情况,收集反馈",
        "assignee": "user_sales_001",
        "due_date": "2026-07-15",
        "priority": 3,
        "status": "completed",
        "created_by": "user_sales_001",
        "created_at": "2026-07-01",
    },
    "CT-EXIST002": {
        "task_id": "CT-EXIST002",
        "customer_id": "C005",
        "title": "定制需求跟进",
        "description": "跟进定制开发进度,确认交付时间",
        "assignee": "user_sales_002",
        "due_date": "2026-08-05",
        "priority": 4,
        "status": "in_progress",
        "created_by": "user_sales_002",
        "created_at": "2026-07-10",
    },
}


# ============ 工具实现 ============


class QueryCustomerTool(BaseTool):
    """查询客户信息(QUERY 类)"""

    name = "query_customer"
    category = ToolCategory.QUERY
    description = "查询客户基本信息、联系人、等级、累计销售额"
    input_schema = QueryCustomerSchema

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        customer_id = params["customer_id"]
        fields = params.get("fields")

        # Mock: 模拟 API 调用延迟
        await asyncio.sleep(0.1)

        customer = _MOCK_CUSTOMERS.get(customer_id)
        if customer is None:
            return ToolResult(
                success=False,
                tool_name=self.name,
                output={},
                error=f"客户不存在: {customer_id}",
            )

        # 字段过滤
        if fields:
            customer = {k: v for k, v in customer.items() if k in fields or k == "customer_id"}

        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"customer": customer},
        )


class QueryOrderTool(BaseTool):
    """查询订单信息(QUERY 类)"""

    name = "query_order"
    category = ToolCategory.QUERY
    description = "查询订单详情,含金额、状态、明细"
    input_schema = QueryOrderSchema

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        order_id = params["order_id"]
        include_items = params.get("include_items", False)

        await asyncio.sleep(0.1)

        order = _MOCK_ORDERS.get(order_id)
        if order is None:
            return ToolResult(
                success=False,
                tool_name=self.name,
                output={},
                error=f"订单不存在: {order_id}",
            )

        result = {k: v for k, v in order.items() if k != "items" or include_items}
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"order": result},
        )


class CreateCrmTaskTool(BaseTool):
    """创建 CRM 跟进任务(ACTION 类,需 Saga 补偿)"""

    name = "create_crm_task"
    category = ToolCategory.ACTION
    description = "在 CRM 系统创建客户跟进任务(有副作用,Saga 可回滚)"
    input_schema = CreateCrmTaskSchema

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        # assignee 缺省(含 LLM 显式给 null)时回填发起人
        if not params.get("assignee"):
            params["assignee"] = context.get("user_id", "system")
        # Mock: 生成任务 ID 并存储
        task_id = f"CT-{uuid.uuid4().hex[:8].upper()}"
        task = {
            "task_id": task_id,
            **params,
            "status": "open",
            "created_by": context.get("user_id", "system"),
            "created_at": "2026-07-26",
        }

        await asyncio.sleep(0.15)
        _mock_crm_tasks[task_id] = task

        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"task": task},
            side_effects={"created_task_id": task_id},
            # 补偿上下文:Saga 回滚时用 task_id 删除任务
            compensation_data={"task_id": task_id, "action": "delete"},
        )

    async def compensate(self, compensation_data: dict[str, Any]) -> ToolResult:
        """补偿:删除已创建的 CRM 任务"""
        task_id = compensation_data.get("task_id")
        if task_id and task_id in _mock_crm_tasks:
            del _mock_crm_tasks[task_id]
            logger.info(f"CRM 任务补偿: 已删除 task_id={task_id}")
            return ToolResult(
                success=True,
                tool_name=self.name,
                output={"message": f"任务 {task_id} 已回滚删除"},
            )
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message": f"任务 {task_id} 不存在,无需补偿"},
        )


# ============ 只读数据访问(供 AnalysisAgent 聚合分析用) ============


def get_all_customers() -> list[dict]:
    """获取全部客户数据(返回字典副本,调用方修改不影响 Mock 源数据)"""
    return [dict(c) for c in _MOCK_CUSTOMERS.values()]


def get_all_orders() -> list[dict]:
    """获取全部订单数据(返回字典副本,含 items 明细,调用方修改不影响源数据)"""
    return [
        {**o, "items": [dict(item) for item in o.get("items", [])]}
        for o in _MOCK_ORDERS.values()
    ]
