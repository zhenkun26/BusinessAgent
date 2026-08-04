"""邮件工具(对接内部邮件系统 + 外部 SMTP)

工具列表:
- send_email_internal: 发送内部邮件(ACTION 类,需 Saga 补偿)
- send_email_external: 发送外部邮件(ACTION 类,需 Saga 补偿 + 更严格 RBAC)

W7 阶段用 Mock 实现,接口契约对应真实邮件 API:
- POST /api/v1/mail/send (内部)
- SMTP/外部 API (外部)

权限设计:
- send_email_internal: salesperson/customer_service/finance/manager 均可用
- send_email_external: 仅 manager/admin 可用(防止数据外泄)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field, field_validator

from app.tools.base import BaseTool, ToolCategory, ToolResult


# ============ Schemas ============


class SendEmailSchema(BaseModel):
    """发送邮件入参(内部/外部共用)"""

    to: list[str] = Field(description="收件人邮箱列表", min_length=1, max_length=50)
    subject: str = Field(description="邮件主题", max_length=500)
    body: str = Field(description="邮件正文", max_length=20000)
    cc: Optional[list[str]] = Field(default=None, description="抄送列表")
    attachments: Optional[list[str]] = Field(default=None, description="附件路径列表")

    @field_validator("to", "cc", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v):
        """LLM 常把单个收件人输出为字符串,统一包装为列表"""
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("to", "cc")
    @classmethod
    def addresses_must_be_valid(cls, v):
        """收件地址语义校验:拒绝空串/无 @ 的无效地址。

        LLM 在收件人未知时可能输出 "" 或 ["收件人姓名"] 兜底,
        这类参数批准后按冻结负载执行必失败,必须在入口处拦下。
        """
        if v is None:
            return v
        for addr in v:
            if not isinstance(addr, str) or not addr.strip() or "@" not in addr:
                raise ValueError(f"无效的收件人地址: {addr!r}(需为含 @ 的邮箱地址)")
        return v

    @field_validator("subject", "body")
    @classmethod
    def no_html_injection(cls, v: str) -> str:
        """简单 HTML 注入防护(防止邮件 XSS)"""
        dangerous_tags = ["<script", "<iframe", "<object", "<embed"]
        lowered = v.lower()
        for tag in dangerous_tags:
            if tag in lowered:
                raise ValueError(f"邮件内容含危险标签: {tag}")
        return v


# ============ Mock 存储 ============


_mock_sent_emails: dict[str, dict] = {}


# ============ 工具实现 ============


class SendEmailInternalTool(BaseTool):
    """发送内部邮件(ACTION 类)"""

    name = "send_email_internal"
    category = ToolCategory.ACTION
    description = "发送内部邮件给同事(仅内部域名,如 @company.internal)"
    input_schema = SendEmailSchema

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        to_list = params["to"]

        # 校验收件人必须是内部域名
        internal_domain = ".internal"
        external = [addr for addr in to_list if not addr.endswith(internal_domain)]
        if external:
            return ToolResult(
                success=False,
                tool_name=self.name,
                output={},
                error=f"内部邮件工具不允许外部地址: {external}",
            )

        # Mock 发送
        message_id = f"INT-{uuid.uuid4().hex[:12].upper()}"
        email_record = {
            "message_id": message_id,
            "from": f"{context.get('user_id', 'system')}@company.internal",
            "to": to_list,
            "cc": params.get("cc", []),
            "subject": params["subject"],
            "body_preview": params["body"][:200],
            "type": "internal",
            "status": "sent",
        }

        await asyncio.sleep(0.2)
        _mock_sent_emails[message_id] = email_record

        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message_id": message_id, "recipients": len(to_list)},
            side_effects={"sent_message_id": message_id},
            compensation_data={"message_id": message_id, "action": "recall"},
        )

    async def compensate(self, compensation_data: dict[str, Any]) -> ToolResult:
        """补偿:撤回邮件(Mock:标记为 recalled)"""
        message_id = compensation_data.get("message_id")
        if message_id and message_id in _mock_sent_emails:
            _mock_sent_emails[message_id]["status"] = "recalled"
            logger.info(f"邮件补偿: 已撤回 message_id={message_id}")
            return ToolResult(
                success=True,
                tool_name=self.name,
                output={"message": f"邮件 {message_id} 已撤回"},
            )
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message": f"邮件 {message_id} 不存在,无需补偿"},
        )


class SendEmailExternalTool(BaseTool):
    """发送外部邮件(ACTION 类,严格 RBAC:仅 manager/admin)"""

    name = "send_email_external"
    category = ToolCategory.ACTION
    description = "发送外部邮件(对外客户/合作伙伴,需 manager/admin 权限)"
    input_schema = SendEmailSchema
    # 高风险操作:执行前需经理审批(审批通过后服务端自动执行)
    requires_approval = True
    risk_level = "high"

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        to_list = params["to"]

        # Mock 发送外部邮件
        message_id = f"EXT-{uuid.uuid4().hex[:12].upper()}"
        email_record = {
            "message_id": message_id,
            "from": f"{context.get('user_id', 'system')}@company.com",
            "to": to_list,
            "cc": params.get("cc", []),
            "subject": params["subject"],
            "body_preview": params["body"][:200],
            "type": "external",
            "status": "sent",
            "audit_note": "外部邮件发送,已记录审计日志",
        }

        await asyncio.sleep(0.3)  # 外部邮件稍慢
        _mock_sent_emails[message_id] = email_record

        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message_id": message_id, "recipients": len(to_list)},
            side_effects={"sent_message_id": message_id},
            compensation_data={"message_id": message_id, "action": "recall"},
        )

    async def compensate(self, compensation_data: dict[str, Any]) -> ToolResult:
        """补偿:撤回外部邮件(实际场景可能无法撤回,标记为审计事件)"""
        message_id = compensation_data.get("message_id")
        if message_id and message_id in _mock_sent_emails:
            _mock_sent_emails[message_id]["status"] = "recall_requested"
            logger.warning(
                f"外部邮件补偿: 撤回请求 message_id={message_id}(外部邮件可能无法完全撤回)"
            )
            return ToolResult(
                success=True,
                tool_name=self.name,
                output={"message": f"外部邮件 {message_id} 撤回请求已提交"},
            )
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"message": f"邮件 {message_id} 不存在,无需补偿"},
        )
