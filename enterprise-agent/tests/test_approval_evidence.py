"""Read-only evidence authorization and redaction; no provider/database acceptance."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.api import approval


@pytest.mark.parametrize('identity,role,allowed', [
    ('owner','salesperson',True), ('decider','manager',True),
    ('another','manager',True), ('another','admin',False), ('another','salesperson',False)])
async def test_evidence_is_authorized_payload_free_and_never_releases(monkeypatch, identity, role, allowed):
    row=NS(approval_id='a',requester_id='owner',approver_id='decider',
           approver_roles=['manager'],status='execution_unknown')
    monkeypatch.setattr(approval.deadline,'load',AsyncMock(return_value=row))
    monkeypatch.setattr(approval,'resolve_active_user',AsyncMock(return_value=NS(role=role)))
    record={'operation_id':'op','execution_id':'exec','state':'unknown', 'updated_at':None,
            'intent':{'target':{'provider':'mock'},'params':{'body':'PRIVATE-BUSINESS'}},
            'request':{'secret':'PRIVATE-BUSINESS'},'receipt':{'success':True,'output':{'body':'PRIVATE-BUSINESS'}}}
    db=NS(execute=AsyncMock(return_value=NS(mappings=lambda:NS(all=lambda:[record]))),
          commit=AsyncMock(),rollback=AsyncMock())
    if not allowed:
        with pytest.raises(HTTPException) as caught:
            await approval.approval_evidence('a',NS(user_id=identity),db)
        assert caught.value.status_code == 403
        db.execute.assert_not_awaited()
    else:
        result=await approval.approval_evidence('a',NS(user_id=identity),db)
        assert result['human_review_required'] and result['status']=='execution_unknown'
        assert result['automatic_release'] is False and result['automatic_retry'] is False
        assert result['operations'][0]['receipt_verified'] is True
        assert 'PRIVATE-BUSINESS' not in repr(result)
        assert 'SELECT' in str(db.execute.await_args.args[0])
    assert row.status=='execution_unknown'
    db.commit.assert_not_awaited(); db.rollback.assert_not_awaited()


async def test_evidence_inactive_actor_never_reads_operations(monkeypatch):
    monkeypatch.setattr(approval.deadline,'load',AsyncMock(return_value=NS(
        requester_id='owner',approver_id='decider',approver_roles=['manager'])))
    monkeypatch.setattr(approval,'resolve_active_user',AsyncMock(side_effect=HTTPException(401,'disabled')))
    db=NS(execute=AsyncMock())
    with pytest.raises(HTTPException): await approval.approval_evidence('a',NS(user_id='owner'),db)
    db.execute.assert_not_awaited()

@pytest.mark.parametrize('receipt', [None, {}, {'success':False}, {'success':1}])
async def test_unverified_evidence_is_never_reported_as_verified(monkeypatch, receipt):
    row=NS(approval_id='a',requester_id='owner',approver_id=None,approver_roles=['manager'],status='execution_unknown')
    monkeypatch.setattr(approval.deadline,'load',AsyncMock(return_value=row))
    monkeypatch.setattr(approval,'resolve_active_user',AsyncMock(return_value=NS(role='salesperson')))
    record={'operation_id':'op','execution_id':'exec','state':'unknown','updated_at':None,
            'intent':{'target':{'provider':'mock'}},'request':{},'receipt':receipt}
    db=NS(execute=AsyncMock(return_value=NS(mappings=lambda:NS(all=lambda:[record]))))
    result=await approval.approval_evidence('a',NS(user_id='owner'),db)
    assert result['operations'][0]['receipt_verified'] is False
    assert result['human_review_required'] and result['automatic_release'] is False


async def test_mixed_query_action_approval_rejects_before_any_preparation(monkeypatch):
    from app.agents import execution
    from app.tools import operation_gateway
    from app.core.tool_operations import OperationError
    tools={'query':NS(category=NS(value='query'),risk_level='low'),
           'action':NS(category=NS(value='action'),risk_level='high')}
    monkeypatch.setattr(execution,'get_tool',tools.get)
    prepare=AsyncMock()
    monkeypatch.setattr(operation_gateway,'prepare_calls',prepare)
    agent=object.__new__(execution.ExecutionAgent)
    plans=[execution.ToolCallPlan(tool=name,params={}) for name in tools]
    with pytest.raises(OperationError,match='APPROVAL_MIXED_QUERY_ACTION'):
        await agent._create_approval_request(plans,{'user_id':'owner','session_id':'session'},'synthetic')
    prepare.assert_not_awaited()
