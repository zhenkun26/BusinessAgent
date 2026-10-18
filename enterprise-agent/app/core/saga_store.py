"""Retained Saga journal. Short locked transactions; external I/O never holds a lock."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
import uuid

from app.core.tool_operations import OperationError, canonical, fingerprint, safe_payload, valid_uuid

LEASE_SECONDS = 120
TERMINAL = frozenset({'succeeded', 'compensated', 'manual'})


class SagaStore:
    def __init__(self) -> None:
        from app.core.database import get_session_factory
        self.factory = get_session_factory()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Any]:
        try:
            async with asyncio.timeout(10):
                async with self.factory() as session:
                    yield session
                    await session.commit()
        except OperationError:
            raise
        except Exception:
            raise OperationError('SAGA_STORE_UNAVAILABLE') from None

    @staticmethod
    async def query(session: Any, sql: str, args: dict) -> list[dict]:
        from sqlalchemy import text
        result = await session.execute(text(sql), args)
        return [dict(row) for row in result.mappings().all()] if result.returns_rows else []

    async def load(self, saga_id: str) -> dict:
        async with self.transaction() as session:
            rows = await self.query(session, 'SELECT * FROM saga_runs WHERE saga_id = :sid',
                                    {'sid': valid_uuid(saga_id)})
            if not rows:
                raise OperationError('SAGA_JOURNAL_REQUIRED')
            steps = await self.query(session,
                'SELECT * FROM saga_steps WHERE saga_id = :sid ORDER BY slot', {'sid': saga_id})
            definitions = [step['definition'] for step in steps]
            if (not steps or rows[0]['plan_hash'] != fingerprint({
                    'steps': definitions, 'context': rows[0]['context']})
                    or any(step['slot'] != slot or str(step['operation_id']) !=
                           step['definition']['operation_id'] for slot, step in enumerate(steps))):
                raise OperationError('SAGA_JOURNAL_INVALID')
            return {**rows[0], 'steps': steps}

    async def prepare(self, definitions: list[dict], context: dict, owner: str) -> tuple[dict, bool]:
        from app.core.task_queue import enqueue_task
        if not definitions or len({d['step_id'] for d in definitions}) != len(definitions):
            raise OperationError('SAGA_PLAN_INVALID')
        identity = {key: context[key] for key in ('user_id', 'role', 'session_id')}
        safe_payload(identity)
        safe_payload(definitions)
        digest = fingerprint({'steps': definitions, 'context': identity})
        first_id = valid_uuid(definitions[0]['operation_id'])
        async with self.transaction() as session:
            # Same lock used by forward claims: attachment cannot race a dispatch.
            executions = await self.query(session, '''SELECT e.* FROM tool_executions e
                JOIN tool_operations o USING (execution_id) WHERE o.operation_id = :oid
                FOR UPDATE OF e''', {'oid': first_id})
            if not executions:
                raise OperationError('SAGA_PLAN_INVALID')
            execution = executions[0]
            sid = str(execution['execution_id'])
            calls = execution['calls']
            if (execution['owner_id'] != identity['user_id']
                    or execution['session_id'] != identity['session_id']
                    or len(calls) != len(definitions)):
                raise OperationError('SAGA_PLAN_CONFLICT')
            for call, definition in zip(calls, definitions, strict=True):
                if any(call[key] != definition[key] for key in ('tool', 'params', 'operation_id')):
                    raise OperationError('SAGA_PLAN_CONFLICT')
            rows = await self.query(session, '''INSERT INTO saga_runs
                (saga_id, context, plan_hash, state, owner_token, lease_until)
                VALUES (:sid, CAST(:context AS JSONB), :hash, 'forward', :owner,
                    clock_timestamp() + :lease * interval '1 second')
                ON CONFLICT (saga_id) DO NOTHING RETURNING saga_id''', {
                    'sid': sid, 'context': canonical(identity), 'hash': digest,
                    'owner': owner, 'lease': LEASE_SECONDS})
            created = bool(rows)
            if created:
                for slot, definition in enumerate(definitions):
                    await self.query(session, '''INSERT INTO saga_steps
                        (saga_id, slot, operation_id, definition, compensation_id)
                        VALUES (:sid, :slot, :oid, CAST(:definition AS JSONB), :cid)''', {
                            'sid': sid, 'slot': slot, 'oid': definition['operation_id'],
                            'definition': canonical(definition), 'cid': str(uuid.uuid4())})
                await enqueue_task(session, 'tasks:saga_retry', 'saga:' + sid, {'saga_id': sid})
                await self._delay_job(session, sid)
            else:
                current = await self.query(session,
                    'SELECT plan_hash FROM saga_runs WHERE saga_id = :sid', {'sid': sid})
                if current[0]['plan_hash'] != digest:
                    raise OperationError('SAGA_PLAN_CONFLICT')
        return await self.load(sid), created

    async def _delay_job(self, session: Any, saga_id: str) -> None:
        await self.query(session, '''UPDATE task_jobs SET available_at =
            clock_timestamp() + :lease * interval '1 second'
            WHERE scope_key = :scope AND state = 'pending' ''',
            {'scope': 'saga:' + saga_id, 'lease': LEASE_SECONDS})

    async def owned(self, session: Any, saga_id: str, owner: str) -> dict:
        rows = await self.query(session, '''SELECT * FROM saga_runs WHERE saga_id = :sid
            AND owner_token = :owner AND lease_until > clock_timestamp()
            AND state IN ('forward', 'aborting') FOR UPDATE''', {'sid': saga_id, 'owner': owner})
        if not rows:
            raise OperationError('SAGA_OWNERSHIP_LOST')
        return rows[0]

    async def acquire(self, saga_id: str, owner: str) -> bool:
        async with self.transaction() as session:
            rows = await self.query(session, '''UPDATE saga_runs SET owner_token = :owner,
                lease_until = clock_timestamp() + :lease * interval '1 second'
                WHERE saga_id = :sid AND state IN ('forward', 'aborting')
                AND (lease_until IS NULL OR lease_until <= clock_timestamp()) RETURNING saga_id''',
                {'sid': valid_uuid(saga_id), 'owner': owner, 'lease': LEASE_SECONDS})
            return bool(rows)

    async def renew(self, saga_id: str, owner: str) -> None:
        async with self.transaction() as session:
            await self.owned(session, saga_id, owner)
            await self.query(session, '''UPDATE saga_runs SET
                lease_until = clock_timestamp() + :lease * interval '1 second',
                updated_at = clock_timestamp() WHERE saga_id = :sid''',
                {'sid': saga_id, 'lease': LEASE_SECONDS})
            await self._delay_job(session, saga_id)

    async def record(self, saga_id: str, owner: str, slot: int, result: dict) -> None:
        safe_payload(result)
        async with self.transaction() as session:
            run = await self.owned(session, saga_id, owner)
            if run['state'] != 'forward':
                raise OperationError('SAGA_OWNERSHIP_LOST')
            await self.query(session, '''UPDATE saga_steps SET result = CAST(:result AS JSONB)
                WHERE saga_id = :sid AND slot = :slot AND result IS NULL''',
                {'sid': saga_id, 'slot': slot, 'result': canonical(result)})

    async def abort(self, saga_id: str, owner: str) -> None:
        async with self.transaction() as session:
            await self.owned(session, saga_id, owner)
            await self.query(session, "UPDATE saga_runs SET state = 'aborting' WHERE saga_id = :sid",
                             {'sid': saga_id})
            # A dispatch claim takes the run lock first. Prepared means no write was claimed.
            await self.query(session, '''UPDATE tool_operations SET state = 'rejected'
                WHERE execution_id = :sid AND state = 'prepared' ''', {'sid': saga_id})

    async def finish(self, saga_id: str, owner: str, state: str, error: str | None = None) -> None:
        if state not in TERMINAL or error not in {None, 'SAGA_MANUAL_REQUIRED'}:
            raise OperationError('SAGA_STATE_INVALID')
        async with self.transaction() as session:
            await self.owned(session, saga_id, owner)
            await self.query(session, '''UPDATE saga_runs SET state = :state, error_code = :error,
                owner_token = NULL, lease_until = NULL, updated_at = clock_timestamp()
                WHERE saga_id = :sid''', {'sid': saga_id, 'state': state, 'error': error})
            await self.query(session, '''UPDATE task_jobs SET state = :state, error_code = :error,
                updated_at = clock_timestamp() WHERE scope_key = :scope AND state = 'pending' ''',
                {'scope': 'saga:' + saga_id, 'state': 'dead' if state == 'manual' else 'done',
                 'error': 'SAGA_MANUAL_REQUIRED' if state == 'manual' else None})

    async def release(self, saga_id: str, owner: str) -> None:
        async with self.transaction() as session:
            await self.owned(session, saga_id, owner)
            await self.query(session, '''UPDATE saga_runs SET owner_token = NULL, lease_until = NULL,
                error_code = 'SAGA_OUTCOME_UNKNOWN', updated_at = clock_timestamp()
                WHERE saga_id = :sid''', {'sid': saga_id})

    async def inverse_claim(self, saga_id: str, owner: str, slot: int, request: dict) -> bool:
        safe_payload(request)
        async with self.transaction() as session:
            run = await self.owned(session, saga_id, owner)
            if run['state'] != 'aborting':
                raise OperationError('SAGA_STATE_INVALID')
            rows = await self.query(session, '''UPDATE saga_steps SET
                compensation_request = CAST(:request AS JSONB), compensation_state = 'dispatched'
                WHERE saga_id = :sid AND slot = :slot AND compensation_state = 'prepared'
                AND compensation_request IS NULL RETURNING compensation_id''',
                {'sid': saga_id, 'slot': slot, 'request': canonical(request)})
            return bool(rows)

    async def inverse_finish(self, saga_id: str, owner: str, slot: int, state: str,
                             receipt: dict | None) -> None:
        if state not in {'committed', 'unknown', 'rejected'}:
            raise OperationError('SAGA_STATE_INVALID')
        safe_payload(receipt)
        async with self.transaction() as session:
            await self.owned(session, saga_id, owner)
            rows = await self.query(session, '''UPDATE saga_steps SET compensation_state = :state,
                compensation_receipt = CAST(:receipt AS JSONB)
                WHERE saga_id = :sid AND slot = :slot
                AND compensation_state IN ('dispatched', 'unknown') RETURNING compensation_id''',
                {'sid': saga_id, 'slot': slot, 'state': state, 'receipt': canonical(receipt)})
            if not rows:
                raise OperationError('SAGA_STATE_CONFLICT')
