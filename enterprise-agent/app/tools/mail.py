"""邮件工具(对接内部邮件系统 + 外部 SMTP)

工具列表:
- send_email_internal: 发送内部邮件(ACTION 类,需 Saga 补偿)
- send_email_external: 发送外部邮件(ACTION 类,需 Saga 补偿 + 更严格 RBAC)

W7 阶段用 Mock 实现,接口契约对应真实邮件 API:
- POST /api/v1/mail/send (内部)
- SMTP/外部 API (外部)

权限设计:
- send_email_internal: salesperson/customer_service/finance/manager 均可用
- send_email_external: 销售、经理与管理员可发起，发送前需审批
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field, field_validator

from app.tools.base import BaseTool, ToolCategory, ToolResult


# ============ Schemas ============

# Provider payloads accept one bare mailbox per list item, never an address header.
_LOCAL_ATOM = r"[\w!#$%&'*+/=?^`{|}~-]+"
_DOMAIN_LABEL = r"[^\W_]+(?:-+[^\W_]+)*"
_MAILBOX = re.compile(rf"{_LOCAL_ATOM}(?:\.{_LOCAL_ATOM})*@{_DOMAIN_LABEL}(?:\.{_DOMAIN_LABEL})*")


def has_external_recipient(params: dict[str, Any], *, provider: str | None = None) -> bool:
    """Classify a plan before RBAC. The schema separately rejects malformed inputs."""
    from app.config import get_settings
    settings = get_settings()
    effective_provider = provider or settings.mail_tool_provider or settings.tool_provider
    reference_profile = (effective_provider == "http"
                         and settings.tool_reference_profile == "business-reference-v1")

    def is_internal(address: str) -> bool:
        # Synthetic capture recipients are never a production domain allowlist.
        if reference_profile:
            return address in {"employee@reference.invalid", "manager@reference.invalid"}
        return address.rpartition("@")[2].lower() == "company.internal"

    for field in ("to", "cc"):
        addresses = params.get(field)
        if isinstance(addresses, str):
            addresses = [addresses]
        if isinstance(addresses, (list, tuple)) and any(
            isinstance(address, str) and "@" in address
            and not is_internal(address)
            for address in addresses
        ):
            return True
    return False


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
        """每项为一个独立邮箱，拒绝拼接地址、显示名及注入的邮件头。"""
        if v is None:
            return v
        for addr in v:
            if not _MAILBOX.fullmatch(addr):
                raise ValueError("每个收件人地址项须为一个完整的邮箱地址")
        return v

    @field_validator("subject")
    @classmethod
    def subject_is_single_line(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("邮件主题须为单行")
        return value

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
    provider_config_attr = "mail_tool_provider"

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        validated = super()._validate_params(params)
        if has_external_recipient(validated, provider=self._effective_provider()):
            raise ValueError("内部邮件工具不允许外部地址（含抄送）")
        return validated

    async def _call_external(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        from app.tools.operation_gateway import invoke_action
        return await invoke_action(self, params, context)

    async def _execute(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        to_list = params["to"]

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
        if compensation_data.get("provider") == "http" or self._effective_provider() == "http":
            return ToolResult(False, self.name, {}, error="DURABLE_COMPENSATION_REQUIRED")
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
    """发送外部邮件（ACTION 类，受角色权限与审批约束）"""

    name = "send_email_external"
    category = ToolCategory.ACTION
    description = "发送外部邮件给客户或合作伙伴（需审批）"
    input_schema = SendEmailSchema
    provider_config_attr = "mail_tool_provider"
    # Approval and subsequent requester confirmation are both required.
    requires_approval = True
    risk_level = "high"

    async def _call_external(self, params: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        from app.tools.operation_gateway import invoke_action
        return await invoke_action(self, params, context)

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
        if compensation_data.get("provider") == "http" or self._effective_provider() == "http":
            return ToolResult(False, self.name, {}, error="DURABLE_COMPENSATION_REQUIRED")
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
