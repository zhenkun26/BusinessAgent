"""C10-R1/R2 regressions: real serializer, actual handlers, isolated store doubles."""
from __future__ import annotations

import ast
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Optional
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pydantic import BaseModel, Field
from langgraph.checkpoint.redis.jsonplus_redis import JsonPlusRedisSerializer

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: str) -> ModuleType:
    result = ModuleType(name)
    result.__file__ = str(ROOT / path)
    exec(compile((ROOT / path).read_bytes(), str(ROOT / path), 'exec'), result.__dict__)
    return result


def source_model() -> ModuleType:
    """Use the unchanged production model without importing model/database clients."""
    result = ModuleType('app.agents.knowledge')
    result.__dict__.update(BaseModel=BaseModel, Field=Field, datetime=datetime, Optional=Optional)
    tree = ast.parse((ROOT / 'app/agents/knowledge.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RetrievalSource')
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/agents/knowledge.py', 'exec',
                 dont_inherit=True),
         result.__dict__)
    return result


class CitationProjectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.knowledge = source_model()
        self.source = self.knowledge.RetrievalSource(
            document_id='doc-1', chunk_id='chunk-1', title='Policy',
            source_url='https://example.invalid/policy', namespace='sales', score=.9,
            updated_at=datetime(2026, 10, 19, tzinfo=timezone.utc))
        self.expected = self.source.model_dump(mode='json')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules, {'app.agents.knowledge': self.knowledge}))
        self.access = load('followup_access', 'app/graph/checkpoint_access.py')
        self.serializer = JsonPlusRedisSerializer()

    def roundtrip(self) -> Any:
        return self.serializer.loads_typed(self.serializer.dumps_typed([self.source]))[0]

    def test_real_redis_roundtrip_has_public_fields(self) -> None:
        restored = self.roundtrip()
        self.assertEqual(restored['type'], 'constructor')
        self.assertEqual(restored['id'], ['app', 'agents', 'knowledge', 'RetrievalSource'])
        self.assertEqual(self.access.normalize_sources([restored]), [self.expected])

    def test_model_plain_and_legacy_envelope_are_equivalent(self) -> None:
        for value in [self.source, self.source.model_dump(), self.expected,
                      {**self.roundtrip(), 'lc': 1}]:
            with self.subTest(kind=type(value).__name__):
                result = self.access.normalize_sources([value])
                self.assertEqual(result, [self.expected])
                json.dumps(result, allow_nan=False)

    def test_only_public_fields_survive(self) -> None:
        self.assertEqual(self.access.normalize_sources([
            {**self.expected, 'internal_secret': 'PRIVATE_TEST_DATA'}]), [self.expected])

    def test_malformed_sources_fail_without_partial_projection(self) -> None:
        for value in [None, {}, 'bad', [None], [{}], [42],
                      [{**self.expected, 'score': float('nan')}],
                      [{**self.expected, 'updated_at': 'invalid'}],
                      [{**self.roundtrip(), 'id': ['os', 'system']}],
                      [{**self.roundtrip(), 'lc': 99}],
                      [{**self.roundtrip(), 'kwargs': []}],
                      [{'kwargs': self.expected}],
                      [self.expected, {'document_id': 'PRIVATE_TEST_DATA'}]]:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(self.access.CheckpointUnavailable) as caught:
                    self.access.normalize_sources(value)
                self.assertEqual(str(caught.exception), 'CHECKPOINT_UNAVAILABLE')

    async def test_invalid_sources_prevent_publication(self) -> None:
        user = SimpleNamespace(request_id='r', user_id='u', conversation_id='s',
                               role='salesperson', department='sales')
        state = {'user_input': vars(user), 'request_id': 'r', 'answer_request_id': 'r',
                 'final_answer': 'answer', 'sources': [{}]}
        cp = SimpleNamespace(aget_tuple=AsyncMock(return_value=SimpleNamespace(
            checkpoint={'id': 'cp', 'channel_values': state})))
        fence = SimpleNamespace(config={}, finish=AsyncMock(), thread_id='physical')
        runtime = load('followup_runtime', 'app/core/runtime_state.py')
        with patch.dict(sys.modules, {'app.core.runtime_state': runtime}):
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.access.publish_checkpoint(cp, 'redis', fence, user)
        fence.finish.assert_not_awaited()

    async def check_handlers(self, source: Any, *, invalid: bool = False) -> None:
        c04 = load('followup_c04', 'tests/test_session_ownership.py')
        case = c04.SessionOwnershipTests()
        await case.asyncSetUp()
        try:
            original_run = case.run_graph
            async def run(**kwargs: Any) -> dict:
                state = await original_run(**kwargs)
                state['sources'] = [source]
                return state
            case.graph.side_effect = run
            async def stream(user_input: Any, *, thread_id: str):
                await run(user_input=user_input, thread_id=thread_id)
                yield {'type': 'token', 'data': 'provisional'}
            sys.modules['app.graph.graph'].run_graph_stream = stream
            if invalid:
                with self.assertRaises(c04.HTTPException) as caught:
                    await case.call('message', case.owner)
                self.assertEqual((caught.exception.status_code, caught.exception.detail),
                                 (503, 'CHECKPOINT_UNAVAILABLE'))
            else:
                response = await case.call('message', case.owner)
                self.assertEqual(response.sources, [self.expected])
            events = await case.call('stream', case.owner)
            parsed = [json.loads(text.removeprefix('data: ').strip())
                      async for text in events.events]
            finals = [event for event in parsed if event['type'] == 'final']
            if invalid:
                self.assertEqual(finals, [])
                self.assertIn({'type': 'error', 'data': 'CHECKPOINT_UNAVAILABLE'}, parsed)
                case.lease.fence.finish.assert_not_awaited()
                with self.assertRaises(c04.HTTPException) as caught:
                    await case.call('history', case.owner)
                self.assertEqual(caught.exception.status_code, 503)
            else:
                self.assertEqual(finals[0]['data']['sources'], [self.expected])
                self.assertEqual((await case.call('history', case.owner))['sources'],
                                 [self.expected])
        finally:
            await case.asyncTearDown()

    async def test_message_sse_history_real_serializer_parity(self) -> None:
        await self.check_handlers(self.roundtrip())

    async def test_message_sse_history_model_parity(self) -> None:
        await self.check_handlers(self.source)

    async def test_message_sse_history_plain_parity(self) -> None:
        await self.check_handlers(self.expected)

    async def test_legacy_naive_time_remains_unzoned_through_redis_and_handlers(self) -> None:
        # Its original timezone is unknown; do not silently claim this is UTC.
        self.source.updated_at = datetime(2026, 11, 1, 1, 30, 0, 125000)
        self.expected = self.source.model_dump(mode='json')
        self.assertEqual(self.expected['updated_at'], '2026-11-01T01:30:00.125000')
        restored = self.roundtrip()
        for value in (self.source, self.expected, restored, {**restored, 'lc': 1}):
            self.assertEqual(self.access.normalize_sources([value]), [self.expected])
        await self.check_handlers(restored)

    async def test_aware_offset_is_preserved_through_redis_and_handlers(self) -> None:
        self.source.updated_at = datetime.fromisoformat('2026-10-20T00:15:00.125000+08:00')
        self.expected = self.source.model_dump(mode='json')
        self.assertEqual(self.expected['updated_at'], '2026-10-20T00:15:00.125000+08:00')
        restored = self.roundtrip()
        self.assertEqual(self.access.normalize_sources([restored]), [self.expected])
        await self.check_handlers(restored)

    async def test_malformed_source_handlers_fail_closed(self) -> None:
        await self.check_handlers({}, invalid=True)


class HistorySelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.access = load('history_followup_access', 'app/graph/checkpoint_access.py')
        fencing = ModuleType('app.core.session_fencing')
        self.publications = fencing.publications = AsyncMock(side_effect=self.rows)
        loguru = ModuleType('loguru')
        loguru.logger = Mock()
        self.stack.enter_context(patch.dict(sys.modules, {
            'app.graph.checkpoint_access': self.access,
            'app.core.session_fencing': fencing, 'loguru': loguru}))
        self.history = load('history_followup', 'app/graph/history.py')
        self.user = SimpleNamespace(user_id='u', conversation_id='s', role='salesperson',
                                    department='sales', request_id='current')
        self.items: list[Any] = []
        self.legacy: list[Any] = []
        self.reads: list[str] = []
        self.legacy_limits: list[int] = []
        self.closed = False
        self.cp = SimpleNamespace(aget_tuple=self.read, alist=self.alist)

    def item(self, request: str, **state: Any) -> Any:
        values = {'request_id': request, 'answer_request_id': request,
                  'final_answer': 'answer-' + request,
                  'user_input': {**vars(self.user), 'request_id': request,
                                 'message': 'question-' + request}, **state}
        return SimpleNamespace(checkpoint={'id': request, 'channel_values': values})

    async def rows(self, sid: str, limit: int) -> list[dict]:
        self.assertEqual(sid, 's')
        return [{'backend': 'redis', 'thread_id': 'accepted-' + t.checkpoint['id'],
                 'checkpoint_ns': '', 'checkpoint_id': t.checkpoint['id']}
                for t in self.items[:limit]]

    async def read(self, config: dict) -> Any:
        row = config['configurable']
        self.assertEqual(row['thread_id'], 'accepted-' + row['checkpoint_id'])
        self.reads.append(row['checkpoint_id'])
        return next(t for t in self.items if t.checkpoint['id'] == row['checkpoint_id'])

    async def alist(self, config: dict, limit: int):
        self.assertEqual(config, {'configurable': {'thread_id': 's'}})
        self.legacy_limits.append(limit)
        try:
            for item in self.legacy:  # Intentionally ignores limit; caller must bound it.
                yield item
        finally:
            self.closed = True

    async def history_for(self, **kwargs: Any) -> list[dict]:
        return await self.history.load_recent_history('s', checkpointer=self.cp,
            user_input=self.user, backend='redis', **kwargs)

    async def test_five_rejected_turns_do_not_hide_sixth_valid_answer(self) -> None:
        self.items = [self.item(str(i), answer_request_id=None) for i in range(5)]
        self.items.append(self.item('valid'))
        self.assertEqual(await self.history_for(),
                         [{'user': 'question-valid', 'assistant': 'answer-valid'}])

    async def test_filter_identity_request_and_duplicate_before_counting(self) -> None:
        self.items = [self.item('current'), self.item('no-answer', final_answer='')]
        for field in ('user_id', 'conversation_id', 'role', 'department', 'request_id'):
            bad = self.item('bad-' + field)
            bad.checkpoint['channel_values']['user_input'][field] = 'foreign'
            self.items.append(bad)
        self.items += [self.item('new'), self.item('new'), self.item('old')]
        self.assertEqual([h['assistant'] for h in await self.history_for(max_turns=2)],
                         ['answer-old', 'answer-new'])
        self.assertEqual(self.legacy_limits, [])

    async def test_stop_reading_after_enough_valid_turns(self) -> None:
        self.items = [self.item(str(i)) for i in range(100)]
        result = await self.history_for(max_turns=200)
        self.assertEqual([h['assistant'] for h in result],
                         ['answer-4', 'answer-3', 'answer-2', 'answer-1', 'answer-0'])
        self.assertEqual(self.reads, ['0', '1', '2', '3', '4'])
        self.assertEqual(self.legacy_limits, [])

    async def test_rejected_publications_allow_legacy_eligible_turns(self) -> None:
        self.items = [self.item(str(i), answer_request_id=None) for i in range(5)]
        self.legacy = [self.item('legacy')]
        self.assertEqual((await self.history_for())[0]['assistant'], 'answer-legacy')
        self.assertEqual(self.legacy_limits, [95])
        self.assertTrue(self.closed)

    async def test_count_budget_cannot_jump_to_legacy_or_101st_publication(self) -> None:
        self.items = [self.item(str(i), answer_request_id=None) for i in range(100)]
        self.items.append(self.item('outside-budget'))
        self.legacy = [self.item('legacy')]
        self.assertEqual(await self.history_for(), [])
        self.assertEqual(len(self.reads), 100)
        self.assertEqual(self.legacy_limits, [])

    async def test_budget_is_shared_with_legacy_and_output_stays_chronological(self) -> None:
        self.items = [self.item('latest')] + [
            self.item(str(i), answer_request_id=None) for i in range(97)]
        self.legacy = [self.item('latest'),
                       self.item('older'), self.item('outside-budget')]
        self.assertEqual([h['assistant'] for h in await self.history_for()],
                         ['answer-older', 'answer-latest'])
        self.assertEqual(self.legacy_limits, [2])

    async def test_publication_failure_does_not_fall_back(self) -> None:
        self.publications.side_effect = RuntimeError('PRIVATE_DSN')
        with self.assertRaises(self.access.CheckpointUnavailable) as caught:
            await self.history_for()
        self.assertEqual(str(caught.exception), 'CHECKPOINT_UNAVAILABLE')
        self.assertEqual(self.legacy_limits, [])

    async def test_missing_checkpoint_and_backend_mismatch_fail(self) -> None:
        self.items = [self.item('r')]
        self.cp.aget_tuple = AsyncMock(return_value=None)
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.history_for()
        self.assertEqual(self.legacy_limits, [])
        self.publications.side_effect = None
        self.publications.return_value = [{'backend': 'postgres'}]
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.history_for()

    async def test_legacy_failure_does_not_return_partial_history(self) -> None:
        self.items = [self.item('r')]
        self.cp.alist = Mock(side_effect=RuntimeError('PRIVATE_DSN'))
        with self.assertRaises(self.access.CheckpointUnavailable):
            await self.history_for()

    async def test_deadline_is_shared_with_legacy(self) -> None:
        # Observe the outer deadline and trigger it while the legacy iterator waits.
        original_timeout = asyncio.timeout
        timeouts = []
        def timeout(seconds: float):
            timeouts.append(seconds)
            return original_timeout(seconds)
        self.items = [self.item('r')]
        async def legacy(config: dict, limit: int):
            self.assertEqual(timeouts[0], self.history.HISTORY_TIMEOUT_SECONDS)
            await asyncio.Event().wait()
            yield self.item('unreachable')
        self.cp.alist = legacy
        with patch.object(self.history, 'HISTORY_TIMEOUT_SECONDS', .02), \
                patch.object(asyncio, 'timeout', side_effect=timeout):
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.history_for()

    async def test_publications_and_legacy_share_one_outer_deadline(self) -> None:
        original_timeout = asyncio.timeout
        outer = None
        def timeout(seconds: float):
            nonlocal outer
            scope = original_timeout(seconds)
            if outer is None:
                outer = scope
            return scope
        original_rows = self.rows
        async def rows(sid: str, limit: int):
            self.assertIsNotNone(outer.when())
            return await original_rows(sid, limit)
        async def legacy(config: dict, limit: int):
            # Expire the same scope created before the publication query, without sleeping.
            outer.reschedule(asyncio.get_running_loop().time())
            await asyncio.Event().wait()
            yield self.item('unreachable')
        self.publications.side_effect = rows
        self.cp.alist = legacy
        with patch.object(asyncio, 'timeout', side_effect=timeout):
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.history_for()
        self.assertTrue(outer.expired())

    async def test_legacy_early_stop_closes_iterator(self) -> None:
        visited = []
        async def legacy(config: dict, limit: int):
            try:
                for i in range(100):
                    visited.append(i)
                    yield self.item(str(i))
                raise AssertionError('Must not overread sufficient history')
            finally:
                self.closed = True
        self.cp.alist = legacy
        self.assertEqual(len(await self.history_for(max_turns=2)), 2)
        self.assertEqual(visited, [0, 1])
        self.assertTrue(self.closed)

    async def test_legacy_timeout_closes_iterator(self) -> None:
        async def legacy(config: dict, limit: int):
            try:
                await asyncio.Event().wait()
                yield self.item('unreachable')
            finally:
                self.closed = True
        self.cp.alist = legacy
        with patch.object(self.history, 'HISTORY_TIMEOUT_SECONDS', .01):
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.history_for()
        self.assertTrue(self.closed)

    async def test_publication_timeout_does_not_fall_back(self) -> None:
        async def rows(sid: str, limit: int):
            await asyncio.Event().wait()
        self.publications.side_effect = rows
        with patch.object(self.history, 'HISTORY_TIMEOUT_SECONDS', .01):
            with self.assertRaises(self.access.CheckpointUnavailable):
                await self.history_for()
        self.assertEqual(self.legacy_limits, [])

    async def test_cancellation_propagates(self) -> None:
        self.publications.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.history_for()

    async def test_no_identity_or_nonpositive_limit_does_not_read(self) -> None:
        self.assertEqual(await self.history_for(max_turns=0), [])
        self.assertEqual(await self.history.load_recent_history('s', checkpointer=self.cp), [])
        self.publications.assert_not_awaited()


if __name__ == '__main__':
    unittest.main(verbosity=2)
