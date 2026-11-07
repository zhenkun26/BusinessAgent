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
    captured = {}

    async def dispatch(tool, params, context):
        captured.update(params)
        return mail.ToolResult(True, tool.name, {"message_id": "synthetic-receipt"})

    gateway = AsyncMock(side_effect=dispatch)
    monkeypatch.setattr("app.tools.operation_gateway.invoke_action", gateway)
    monkeypatch.setattr("app.tools.base.get_audit_logger", lambda: AsyncMock())
    result = await tool.invoke(payload, {"role": "customer_service"})

    assert result.success
    gateway.assert_awaited_once()
    assert captured["to"] == [payload["to"]]
    assert captured["cc"] == payload["cc"]


@pytest.mark.parametrize("provider,profile,address,external", [
    ("mock", "business-reference-v1", "employee@reference.invalid", True),
    ("http", "", "employee@reference.invalid", True),
    ("http", "business-reference-v1", "employee@reference.invalid", False),
    ("http", "business-reference-v1", "manager@reference.invalid", False),
    ("http", "business-reference-v1", "customer@reference.invalid", True),
    ("http", "business-reference-v1", "other@reference.invalid", True),
    ("http", "business-reference-v1", "person@company.internal", True),
    ("mock", "", "person@COMPANY.INTERNAL", False),
    ("http", "", "person@other.internal", True),
])
@pytest.mark.parametrize("field", ["to", "cc"])
def test_reference_capture_policy_is_explicit_and_isolated(
    monkeypatch, provider, profile, address, external, field
):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "tool_reference_profile", profile)
    assert mail.has_external_recipient({field: [address]}, provider=provider) is external


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
    agent = execution.ExecutionAgent(role, user_id="synthetic-owner",
        conversation_id="synthetic-session", original_request="Send follow-up")
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

@pytest.mark.parametrize('role,approved', [(AgentRole.SALESPERSON, True),
                                          (AgentRole.CUSTOMER_SERVICE, False)])
async def test_real_parser_normalizes_external_cc_before_schema_and_rechecks_role(monkeypatch, role, approved):
    import json
    from types import SimpleNamespace
    payload = _message(cc=['customer@example.org'])
    model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=json.dumps(
        [{'tool':'send_email_internal','params':payload}]))))
    query = 'Send follow-up to team and copy customer@example.org'
    agent = execution.ExecutionAgent(role, llm=model, user_id='synthetic-owner',
        conversation_id='synthetic-session', original_request=query)
    create = AsyncMock(return_value='synthetic-approval')
    direct = AsyncMock()
    monkeypatch.setattr(agent, '_create_approval_request', create)
    monkeypatch.setattr(execution, 'execute_tool_calls', direct)
    result = await agent.run(query)
    direct.assert_not_awaited()
    if approved:
        assert result.output['stage'] == 'approval_pending'
        create.assert_awaited_once()
        assert create.await_args.args[0][0].tool == 'send_email_external'
    else:
        assert not result.success
        create.assert_not_awaited()
