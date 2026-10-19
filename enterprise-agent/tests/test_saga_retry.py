"""Current retained-journal retry entry; external receipts are covered by C13/C18."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core import saga_retry
from app.core.tool_operations import OperationError

SAGA_ID = "00000000-0000-4000-8000-000000000013"


def journal(monkeypatch: pytest.MonkeyPatch) -> tuple[SimpleNamespace, AsyncMock]:
    """Two confirmed actions under an owned v1 journal, never legacy free-form actions."""
    steps = [dict(slot=slot, operation_id=str(slot), definition={"action": True})
             for slot in range(2)]
    store = SimpleNamespace(
        load=AsyncMock(return_value={"state": "aborting", "steps": steps, "context": {}}),
        acquire=AsyncMock(return_value=True), abort=AsyncMock(), renew=AsyncMock(),
        finish=AsyncMock(), release=AsyncMock(),
    )
    operations = SimpleNamespace(load=AsyncMock(side_effect=lambda oid: {
        "operation_id": oid, "state": "committed", "receipt": {},
        "intent": {"target": {"provider": "http"}},
    }))
    inverse = AsyncMock(return_value="committed")
    monkeypatch.setattr(saga_retry, "SagaStore", lambda: store)
    monkeypatch.setattr(saga_retry, "OperationStore", lambda: operations)
    monkeypatch.setattr(saga_retry.reference, "receipt", Mock())
    monkeypatch.setattr(saga_retry, "compensate_step", inverse)
    return store, inverse


@pytest.mark.asyncio
async def test_should_mark_saga_compensated_when_all_actions_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    store, inverse = journal(monkeypatch)

    assert await saga_retry.retry_saga_compensations(SAGA_ID) == "compensated"

    owner = store.acquire.await_args.args[1]
    assert [c.args[3]["slot"] for c in inverse.await_args_list] == [1, 0]
    assert all(c.args[:3] == (store, SAGA_ID, owner) for c in inverse.await_args_list)
    store.abort.assert_awaited_once_with(SAGA_ID, owner)
    store.finish.assert_awaited_once_with(SAGA_ID, owner, "compensated")
    store.release.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_retain_aborting_when_compensation_is_unconfirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    store, inverse = journal(monkeypatch)
    inverse.return_value = "unknown"

    assert await saga_retry.retry_saga_compensations(SAGA_ID) == "aborting"

    owner = store.acquire.await_args.args[1]
    inverse.assert_awaited_once()
    assert inverse.await_args.args[3]["slot"] == 1
    store.finish.assert_not_awaited()
    store.release.assert_awaited_once_with(SAGA_ID, owner)


@pytest.mark.asyncio
async def test_should_deny_legacy_saga_before_loading_or_executing(monkeypatch: pytest.MonkeyPatch) -> None:
    store, inverse = journal(monkeypatch)
    with pytest.raises(OperationError, match="^ACTION_IDENTITY_INVALID$"):
        await saga_retry.retry_saga_compensations("saga_001")
    store.load.assert_not_awaited()
    store.acquire.assert_not_awaited()
    inverse.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_not_execute_when_journal_is_owned_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    store, inverse = journal(monkeypatch)
    store.acquire.return_value = False
    assert await saga_retry.retry_saga_compensations(SAGA_ID) == "busy"
    store.abort.assert_not_awaited()
    inverse.assert_not_awaited()
    store.finish.assert_not_awaited()
