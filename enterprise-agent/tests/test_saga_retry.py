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
async def test_failed_actions_are_held_without_inverse(monkeypatch: pytest.MonkeyPatch) -> None:
    store, inverse = journal(monkeypatch)
    assert await saga_retry.retry_saga_compensations(SAGA_ID) == "manual"
    owner = store.acquire.await_args.args[1]
    inverse.assert_not_awaited()
    store.abort.assert_awaited_once_with(SAGA_ID, owner)
    store.finish.assert_awaited_once_with(SAGA_ID, owner, "manual", "SAGA_MANUAL_REQUIRED")
    store.release.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_hold_is_terminal_even_with_late_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    store, inverse = journal(monkeypatch)
    store.load.return_value["state"] = "manual"
    assert await saga_retry.retry_saga_compensations(SAGA_ID) == "manual"
    store.acquire.assert_not_awaited()
    inverse.assert_not_awaited()
    store.finish.assert_not_awaited()
    store.release.assert_not_awaited()


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
