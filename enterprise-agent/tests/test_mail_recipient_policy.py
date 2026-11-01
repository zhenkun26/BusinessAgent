"""Exercise recipient policy before approval and before either provider sees a message."""

from unittest.mock import AsyncMock

import pytest

from app.agents import execution
from app.core.approval_notify import _send_internal_mail
from app.security.rbac import AgentRole
from app.tools import mail


def _message(**overrides):
    return {"to": ["team@company.internal"], "subject": "Follow-up", "body": "Details", **overrides}


@pytest.mark.parametrize("provider", ["http", "mock"])
@pytest.mark.parametrize("field,address", [
    ("to", "person@other.internal"),
    ("cc", "person@outside.example"),
    ("cc", "outside@example.org,inside@company.internal"),
    ("to", "outside@example.org;inside@company.internal"),
    ("cc", "inside@company.internal\r\nBcc: outside@example.org"),
    ("to", "outside@example.org@company.internal"),
    ("subject", "Follow-up\r\nBcc: outside@example.org"),
])
async def test_internal_tool_rejects_unsafe_addresses_before_dispatch(
    monkeypatch, provider, field, address
):
    tool = mail.SendEmailInternalTool()
    tool.provider_override = provider
    send_mock, send_http = AsyncMock(), AsyncMock()
    monkeypatch.setattr(tool, "_execute", send_mock)
    monkeypatch.setattr(tool, "_call_external", send_http)
    result = await tool.invoke(_message(**{field: address}), {"role": "customer_service"})

    assert not result.success
    send_mock.assert_not_awaited()
    send_http.assert_not_awaited()


@pytest.mark.parametrize("provider", ["http", "mock"])
async def test_internal_tool_preserves_valid_to_and_cc(monkeypatch, provider):
    tool = mail.SendEmailInternalTool()
    tool.provider_override = provider
    payload = _message(to="Team+1@COMPANY.INTERNAL", cc=["office@company.internal"])
    send_http = AsyncMock(return_value=(True, {"message_id": "from-provider"}, None))
    monkeypatch.setattr(mail, "call_external_api", send_http)
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: AsyncMock())
    monkeypatch.setattr(mail, "_mock_sent_emails", {})
    result = await tool.invoke(payload, {"role": "customer_service"})

    assert result.success
    if provider == "http":
        record = send_http.await_args.kwargs["json_body"]
        assert record["scope"] == "internal"
    else:
        send_http.assert_not_awaited()
        record = mail._mock_sent_emails[result.output["message_id"]]
    assert record["to"] == [payload["to"]]
    assert record["cc"] == payload["cc"]


async def test_notification_rejects_external_stored_mailbox(monkeypatch):
    monkeypatch.setattr(mail, "_mock_sent_emails", {})
    with pytest.raises(ValueError, match="不允许外部地址"):
        await _send_internal_mail("person@other.internal", "approval-1", "executed", "Done")
    assert not mail._mock_sent_emails


@pytest.mark.parametrize("role,expected_stage", [
    (AgentRole.CUSTOMER_SERVICE, "rbac_denied"),
    (AgentRole.FINANCE, "rbac_denied"),
    (AgentRole.SALESPERSON, "approval_pending"),
    (AgentRole.MANAGER, "approval_pending"),
])
async def test_external_cc_requires_external_role_and_approval(monkeypatch, role, expected_stage):
    plan = execution.ToolCallPlan(tool="send_email_internal", params=_message(cc="customer@example.org"))
    agent = execution.ExecutionAgent(role)
    monkeypatch.setattr(agent, "_parse_tool_calls", AsyncMock(return_value=[plan]))
    create_approval = AsyncMock(return_value="approval-1")
    monkeypatch.setattr(agent, "_create_approval_request", create_approval)
    direct = AsyncMock()
    monkeypatch.setattr(execution, "execute_tool_calls", direct)

    result = await agent.run("Send follow-up")

    assert result.output["stage"] == expected_stage
    direct.assert_not_awaited()
    if expected_stage == "approval_pending":
        create_approval.assert_awaited_once()
        submitted = create_approval.await_args.args[0]
        assert [(p.tool, p.params["cc"]) for p in submitted] == [
            ("send_email_external", "customer@example.org")
        ]
    else:
        create_approval.assert_not_awaited()
