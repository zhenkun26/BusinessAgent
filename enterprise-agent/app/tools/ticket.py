"""工单工具(对接工单系统)

工具列表:
- create_ticket: 创建工单(ACTION 类,需 Saga 补偿)
- update_ticket: 更新工单状态(ACTION 类,需 Saga 补偿)

W7 阶段用 Mock 实现,接口契约对应真实工单 API:
- POST /api/v1/tickets
- PATCH /api/v1/tickets/{ticket_id}

权限设计:
- create_ticket: customer_service/manager/admin
- update_ticket: customer_service/manager/admin
(RBAC 在 ROLE_TOOLS 中配置,本工具不重复定义)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field, field_validator

from app.tools.base import BaseTool, ToolCategory, ToolResult


# ============ Schemas ============


class CreateTicketSchema(BaseModel):
    """创建工单入参"""

    title: str = Field(description="工单标题", max_length=200)
    # LLM 工具选择常漏传 description(2026-07-28 实测),给默认值并在执行时用 title 回填
    description: str = Field(default="", description="工单描述", max_length=5000)
    customer_id: Optional[str] = Field(default=None, description="关联客户 ID")
    priority: str = Field(default="normal", description="优先级: low/normal/high/urgent")
    category: str = Field(default="general", description="工单分类")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"low", "normal", "high", "urgent"}
        if v not in allowed:
            raise ValueError(f"priority 必须是 {allowed} 之一")
        return v


class UpdateTicketSchema(BaseModel):
    """更新工单入参"""

    ticket_id: str = Field(description="工单 ID")
    status: Optional[str] = Field(default=None, description="新状态: open/in_progress/resolved/closed")
    priority: Optional[str] = Field(default=None, description="新优先级")
    assignee: Optional[str] = Field(default=None, description="指派给(user_id)")
    comment: Optional[str] = Field(default=None, description="更新备注", max_length=2000)


# ============ Mock 存储 ============


# 预置 6 个历史工单(不同状态/优先级/分类,让 update_ticket 有真实场景)
_mock_tickets: dict[str, dict] = {
    "TK-EXIST001": {
        "ticket_id": "TK-EXIST001",
        "title": "C001 企业版授权到期提醒",
        "description": "客户 C001 的企业版授权将于 30 天后到期,需联系续费",
        "customer_id": "C001",
        "priority": "high",
        "category": "renewal",
        "status": "in_progress",
        "created_by": "user_cs_001",
        "created_at": "2026-07-20",
        "comments": [{"user": "user_cs_001", "text": "已联系张经理,待确认续费方案", "at": "2026-07-21"}],
    },
    "TK-EXIST002": {
        "ticket_id": "TK-EXIST002",
        "title": "C003 标准版功能咨询",
        "description": "客户咨询标准版是否支持批量导入功能",
        "customer_id": "C003",
        "priority": "normal",
        "category": "consultation",
        "status": "open",
        "created_by": "user_cs_002",
        "created_at": "2026-07-24",
    },
    "TK-EXIST003": {
        "ticket_id": "TK-EXIST003",
        "title": "C005 数据分析模块 bug 反馈",
        "description": "客户反馈数据分析模块在导出报表时偶发报错,影响日常使用",
        "customer_id": "C005",
        "priority": "urgent",
        "category": "bug_report",
        "status": "in_progress",
        "created_by": "user_cs_001",
        "created_at": "2026-07-22",
        "comments": [
            {"user": "user_cs_001", "text": "已复现问题,提交技术团队排查", "at": "2026-07-22"},
            {"user": "user_cs_001", "text": "技术团队定位为并发导出时的资源竞争,修复中", "at": "2026-07-23"},
        ],
    },
    "TK-EXIST004": {
        "ticket_id": "TK-EXIST004",
        "title": "C002 退款申请",
        "description": "客户 C002 因业务调整申请退款,订单 ORD-2026-008",
        "customer_id": "C002",
        "priority": "high",
        "category": "refund",
        "status": "open",
        "created_by": "user_cs_002",
        "created_at": "2026-07-25",
    },
    "TK-EXIST005": {
        "ticket_id": "TK-EXIST005",
        "title": "C007 续费方案咨询",
        "description": "客户咨询续费优惠政策及升级方案",
        "customer_id": "C007",
        "priority": "normal",
        "category": "consultation",
        "status": "resolved",
        "created_by": "user_cs_001",
        "created_at": "2026-07-15",
        "comments": [{"user": "user_cs_001", "text": "已提供续费方案,客户确认续费", "at": "2026-07-16"}],
    },
    "TK-EXIST006": {
        "ticket_id": "TK-EXIST006",
        "title": "C004 物流接口对接故障",
        "description": "客户反馈物流接口调用超时,影响发货流程",
        "customer_id": "C004",
        "priority": "urgent",
        "category": "incident",
        "status": "closed",
        "created_by": "user_cs_002",
        "created_at": "2026-07-18",
        "comments": [
            {"user": "user_cs_002", "text": "已定位为网络抖动,临时切换备用通道", "at": "2026-07-18"},
            {"user": "user_cs_002", "text": "网络恢复,接口正常,关闭工单", "at": "2026-07-19"},
        ],
    },
}


# ============ 工具实现 ============


class CreateTicketTool(BaseTool):
    """创建工单(ACTION 类)"""

    name = "create_ticket"
    category = ToolCategory.ACTION
    description = "创建客户服务工单(售后/投诉/咨询等)"
    input_schema = CreateTicketSchema

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        # 校验 priority
        allowed = {"low", "normal", "high", "urgent"}
        if params.get("priority", "normal") not in allowed:
            return ToolResult(
                success=False,
                tool_name=self.name,
                output={},
                error=f"priority 必须是 {allowed} 之一",
            )

        ticket_id = f"TK-{uuid.uuid4().hex[:8].upper()}"
        ticket = {
            "ticket_id": ticket_id,
            "title": params["title"],
            "description": params.get("description") or params["title"],
            "customer_id": params.get("customer_id"),
            "priority": params.get("priority", "normal"),
            "category": params.get("category", "general"),
            "status": "open",
            "created_by": context.get("user_id", "system"),
            "created_at": "2026-07-26",
        }

        await asyncio.sleep(0.15)
        _mock_tickets[ticket_id] = ticket

        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"ticket": ticket},
            side_effects={"created_ticket_id": ticket_id},
            compensation_data={"ticket_id": ticket_id, "action": "close"},
        )

    async def compensate(self, compensation_data: dict[str, Any]) -> ToolResult:
        """补偿:关闭已创建的工单(不删除,保留审计)"""
        ticket_id = compensation_data.get("ticket_id")
        if ticket_id and ticket_id in _mock_tickets:
            _mock_tickets[ticket_id]["status"] = "closed"
            _mock_tickets[ticket_id]["closure_reason"] = "saga_compensation"
            logger.info(f"工单补偿: 已关闭 ticket_id={ticket_id}")
            return ToolResult(
                success=True,
                tool_name=self.name,
                output={"message": f"工单 {ticket_id} 已关闭(补偿)"},
            )
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message": f"工单 {ticket_id} 不存在,无需补偿"},
        )


class UpdateTicketTool(BaseTool):
    """更新工单(ACTION 类)"""

    name = "update_ticket"
    category = ToolCategory.ACTION
    description = "更新工单状态/优先级/指派(需先有工单)"
    input_schema = UpdateTicketSchema

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        ticket_id = params["ticket_id"]

        await asyncio.sleep(0.1)

        ticket = _mock_tickets.get(ticket_id)
        if ticket is None:
            return ToolResult(
                success=False,
                tool_name=self.name,
                output={},
                error=f"工单不存在: {ticket_id}",
            )

        # 记录旧值(供补偿回滚)
        old_values = {}
        update_fields = ["status", "priority", "assignee"]
        for field in update_fields:
            new_val = params.get(field)
            if new_val is not None and new_val != ticket.get(field):
                old_values[field] = ticket.get(field)
                ticket[field] = new_val

        if params.get("comment"):
            ticket.setdefault("comments", []).append(
                {
                    "user": context.get("user_id", "system"),
                    "text": params["comment"],
                    "at": "2026-07-26",
                }
            )

        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"ticket": ticket, "updated_fields": list(old_values.keys())},
            side_effects={"updated_ticket_id": ticket_id},
            compensation_data={
                "ticket_id": ticket_id,
                "action": "restore",
                "old_values": old_values,
            },
        )

    async def compensate(self, compensation_data: dict[str, Any]) -> ToolResult:
        """补偿:恢复工单旧值"""
        ticket_id = compensation_data.get("ticket_id")
        old_values = compensation_data.get("old_values", {})

        if ticket_id and ticket_id in _mock_tickets and old_values:
            for field, old_val in old_values.items():
                _mock_tickets[ticket_id][field] = old_val
            logger.info(f"工单更新补偿: 已恢复 ticket_id={ticket_id}, fields={list(old_values.keys())}")
            return ToolResult(
                success=True,
                tool_name=self.name,
                output={"message": f"工单 {ticket_id} 已恢复旧值"},
            )
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message": f"工单 {ticket_id} 无需恢复"},
        )
