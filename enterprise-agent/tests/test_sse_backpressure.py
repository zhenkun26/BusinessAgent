"""Bounded SSE regressions with real ASGI response code and synthetic transports/stores."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
import json
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api import sse_response
from app.core import sse_stream as stream


def event(text: str = 'x') -> dict:
    return {'type': 'token', 'data': text}


def parse(frame: str) -> dict:
    return json.loads(frame.removeprefix('data: '))


@pytest.mark.asyncio
async def test_item_capacity_blocks_until_consumer_frees_a_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stream, 'MAX_QUEUED_EVENTS', 2)
    channel = stream.SSEChannel()
    await channel.put(event('one'))
    await channel.put(event('two'))
    pending = asyncio.create_task(channel.put(event('three')))
    await asyncio.sleep(0)
    assert not pending.done() and len(channel.frames) == 2
    assert parse(await channel.get())['data'] == 'one'
    await asyncio.wait_for(pending, 1)
    assert [parse(await channel.get())['data'] for _ in range(2)] == ['two', 'three']
    assert channel.buffer_bytes == 0


@pytest.mark.asyncio
async def test_utf8_byte_capacity_is_independent_of_item_count(monkeypatch: pytest.MonkeyPatch) -> None:
    item = event('界😀')
    size = len(stream.encode_event(item).encode())
    monkeypatch.setattr(stream, 'MAX_BUFFER_BYTES', size)
    channel = stream.SSEChannel()
    await channel.put(item)
    pending = asyncio.create_task(channel.put(item))
    await asyncio.sleep(0)
    assert not pending.done() and channel.buffer_bytes == size and len(channel.frames) == 1
    await channel.get()
    await asyncio.wait_for(pending, 1)
    assert channel.buffer_bytes == size
    channel.close()
    assert channel.buffer_bytes == 0


def test_encoded_frame_boundary_includes_sse_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = stream.encode_event(event('界'))
    monkeypatch.setattr(stream, 'MAX_EVENT_BYTES', len(frame.encode()))
    assert stream.encode_event(event('界')) == frame
    with pytest.raises(stream.StreamFailure, match='STREAM_EVENT_TOO_LARGE'):
        stream.encode_event(event('界x'))


@pytest.mark.asyncio
async def test_oversized_event_never_enters_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stream, 'MAX_EVENT_BYTES', 100)
    channel = stream.SSEChannel()
    with pytest.raises(stream.StreamFailure, match='STREAM_EVENT_TOO_LARGE'):
        await channel.put(event('界' * 100))
    assert not channel.frames and channel.buffer_bytes == 0


@pytest.mark.asyncio
async def test_full_buffer_timeout_terminal_bypasses_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stream, 'MAX_QUEUED_EVENTS', 1)
    monkeypatch.setattr(stream, 'BUFFER_WAIT_SECONDS', .02)
    channel = stream.SSEChannel()
    await channel.put(event())
    with pytest.raises(stream.StreamFailure, match='STREAM_BACKPRESSURE_TIMEOUT'):
        await channel.put(event())
    terminal = stream.encode_event({'type': 'error', 'data': 'STREAM_BACKPRESSURE_TIMEOUT'})
    channel.finish(terminal, discard=True)
    assert channel.buffer_bytes == 0
    assert await channel.get() == terminal
    assert await channel.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['error', 'cancelled'])
async def test_failure_terminal_discards_data_and_wakes_waiting_producer(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    monkeypatch.setattr(stream, 'MAX_QUEUED_EVENTS', 1)
    channel = stream.SSEChannel()
    await channel.put(event())
    pending = asyncio.create_task(channel.put(event('blocked')))
    await asyncio.sleep(0)
    channel.finish(stream.encode_event({'type': kind}), discard=True)
    with pytest.raises(stream.StreamFailure, match='STREAM_CLOSED'):
        await asyncio.wait_for(pending, 1)
    assert parse(await channel.get())['type'] == kind
    channel.finish(stream.encode_event({'type': 'final'}))
    assert await channel.get() is None  # first terminal wins, even after consumption


@pytest.mark.asyncio
async def test_success_drains_data_before_exactly_one_final() -> None:
    channel = stream.SSEChannel()
    await channel.put(event('one'))
    await channel.put(event('two'))
    channel.finish(stream.encode_event({'type': 'final', 'data': {}}))
    assert [parse(await channel.get())['type'] for _ in range(3)] == ['token', 'token', 'final']
    assert await channel.get() is None


@pytest.mark.asyncio
async def test_close_wakes_consumer_and_rejects_all_future_admission() -> None:
    channel = stream.SSEChannel()
    pending = asyncio.create_task(channel.get())
    await asyncio.sleep(0)
    channel.close()
    assert await asyncio.wait_for(pending, 1) is None
    with pytest.raises(stream.StreamFailure, match='STREAM_CLOSED'):
        await channel.put(event())
    channel.finish(stream.encode_event({'type': 'final'}))
    assert await channel.get() is None


@pytest.mark.asyncio
async def test_full_buffer_cancelled_put_leaves_accounting_intact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stream, 'MAX_QUEUED_EVENTS', 1)
    channel = stream.SSEChannel()
    await channel.put(event())
    before = channel.buffer_bytes
    pending = asyncio.create_task(channel.put(event()))
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert len(channel.frames) == 1 and channel.buffer_bytes == before
    channel.finish(stream.encode_event({'type': 'cancelled'}), discard=True)
    assert channel.buffer_bytes == 0


@pytest.mark.asyncio
async def test_cleanup_failure_is_observed_and_timeout_does_not_wait_forever(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stream, 'CLEANUP_SECONDS', .02)
    log = Mock()
    monkeypatch.setattr(stream, 'logger', log)
    await stream.bounded_cleanup(AsyncMock(side_effect=RuntimeError('PRIVATE'))())
    await asyncio.sleep(0)
    assert log.warning.call_args.args == ('STREAM_BACKGROUND_TASK_FAILED',)
    stopped = asyncio.Event()
    async def slow() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    await asyncio.wait_for(stream.bounded_cleanup(slow()), 1)
    await asyncio.wait_for(stopped.wait(), 1)
    await asyncio.sleep(0)
    assert any(c.args == ('STREAM_CLEANUP_TIMEOUT',) for c in log.warning.call_args_list)


@pytest.mark.asyncio
async def test_cancellation_resistant_producer_join_is_bounded_and_observed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stream, 'CLEANUP_SECONDS', .02)
    started, release = asyncio.Event(), asyncio.Event()
    async def work() -> None:
        started.set()
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                continue
    task = asyncio.create_task(work())
    stream.observe_task(task)
    await started.wait()
    assert not await asyncio.wait_for(stream.join_producer(task), 1)
    assert task in stream._pending
    release.set()
    await task
    await asyncio.sleep(0)
    assert task not in stream._pending


@pytest.mark.asyncio
@pytest.mark.parametrize('version', ['2.0', '2.4'])
@pytest.mark.parametrize('phase', ['headers', 'body'])
async def test_real_asgi_send_timeout_closes_before_or_during_body(monkeypatch: pytest.MonkeyPatch, version: str, phase: str) -> None:
    monkeypatch.setattr(sse_response, 'SEND_TIMEOUT_SECONDS', .02)
    started, closed = asyncio.Event(), asyncio.Event()
    async def body() -> AsyncIterator[str]:
        started.set()
        try:
            yield stream.encode_event(event())
            await asyncio.Event().wait()
        finally:
            closed.set()
    close = AsyncMock()
    async def send(message: dict) -> None:
        target = 'http.response.start' if phase == 'headers' else 'http.response.body'
        if message['type'] == target:
            await asyncio.Event().wait()
    async def receive() -> dict:
        await asyncio.Event().wait()
    response = sse_response.BoundedStreamingResponse(body(), close=close)
    await asyncio.wait_for(response({'type': 'http', 'asgi': {'spec_version': version}},
                                    receive, send), 1)
    close.assert_awaited_once()
    assert started.is_set() == (phase == 'body')
    assert closed.is_set() == (phase == 'body')


@pytest.mark.asyncio
@pytest.mark.parametrize('version', ['2.0', '2.4'])
async def test_real_asgi_total_lifetime_bounds_silent_producer(monkeypatch: pytest.MonkeyPatch, version: str) -> None:
    monkeypatch.setattr(sse_response, 'STREAM_SECONDS', .02)
    stopped = asyncio.Event()
    async def body() -> AsyncIterator[str]:
        try:
            await asyncio.Event().wait()
            yield stream.encode_event(event())
        finally:
            stopped.set()
    async def receive() -> dict:
        await asyncio.Event().wait()
    close = AsyncMock()
    response = sse_response.BoundedStreamingResponse(body(), close=close)
    await asyncio.wait_for(response({'type': 'http', 'asgi': {'spec_version': version}},
                                    receive, AsyncMock()), 1)
    assert stopped.is_set()
    close.assert_awaited_once()


@pytest.mark.asyncio
async def test_asgi_disconnect_and_broken_pipe_close_response() -> None:
    async def body() -> AsyncIterator[str]:
        yield stream.encode_event(event())
        await asyncio.Event().wait()
    for version in ['2.0', '2.4']:
        close = AsyncMock()
        response = sse_response.BoundedStreamingResponse(body(), close=close)
        receive = AsyncMock(return_value={'type': 'http.disconnect'})
        if version == '2.0':
            await response({'type': 'http', 'asgi': {'spec_version': version}},
                           receive, AsyncMock())
        else:
            await response({'type': 'http', 'asgi': {'spec_version': version}},
                           receive, AsyncMock(side_effect=OSError('synthetic socket closed')))
        close.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_validator_rejects_before_fence_commit() -> None:
    from app.graph.checkpoint_access import publish_checkpoint
    user = SimpleNamespace(request_id='r', user_id='u', conversation_id='s', role='salesperson',
                           department='dept')
    state = {'request_id': 'r', 'user_input': vars(user), 'final_answer': 'x' * 100000}
    cp = SimpleNamespace(aget_tuple=AsyncMock(return_value=SimpleNamespace(
        checkpoint={'id': 'id', 'channel_values': state})))
    fence = SimpleNamespace(config={}, thread_id='t', finish=AsyncMock(return_value=True))
    with pytest.raises(stream.StreamFailure, match='STREAM_EVENT_TOO_LARGE'):
        await publish_checkpoint(cp, 'memory', fence, user,
                                 before_publish=lambda s: stream.encode_event(
                                     {'type': 'final', 'data': s['final_answer']}))
    fence.finish.assert_not_awaited()


@asynccontextmanager
async def chat_fixture() -> AsyncIterator[Any]:
    from test_session_ownership import SessionOwnershipTests
    case = SessionOwnershipTests()
    await case.asyncSetUp()
    try:
        yield case
    finally:
        await case.asyncTearDown()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['full_timeout', 'cancel', 'disconnect'])
async def test_api_full_queue_terminates_without_sentinel_or_late_success(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    monkeypatch.setattr(stream, 'MAX_QUEUED_EVENTS', 1)
    monkeypatch.setattr(stream, 'BUFFER_WAIT_SECONDS', .03 if kind == 'full_timeout' else 2)
    async with chat_fixture() as case:
        entered, stopped = asyncio.Event(), asyncio.Event()
        producer = []
        context = ContextVar('test_prompt_user', default=None)
        case.chat.set_prompt_user = context.set
        reset = Mock(side_effect=context.reset)
        case.chat.reset_prompt_user = reset
        async def graph(*args: Any, **kwargs: Any) -> AsyncIterator[dict]:
            producer.append(asyncio.current_task())
            assert context.get() == case.owner.user_id
            try:
                for i in range(6):
                    if i == 2:
                        entered.set()
                    yield event(str(i))
            finally:
                assert context.get() == case.owner.user_id
                stopped.set()
        with patch.object(sys.modules['app.graph.graph'], 'run_graph_stream', graph):
            response = await case.call('stream', case.owner)
            assert not producer  # response creation does not run the graph
            assert parse(await anext(response.events))['type'] == 'token'
            await asyncio.wait_for(entered.wait(), 1)
            if kind == 'cancel':
                producer[0].cancel()
            elif kind == 'disconnect':
                await asyncio.wait_for(response.events.aclose(), 1)
            await asyncio.wait_for(stopped.wait(), 1)
            if kind != 'disconnect':
                frames = [parse(f) async for f in response.events]
                assert len(frames) == 1
                assert frames[0]['type'] == ('error' if kind == 'full_timeout' else 'cancelled')
                if kind == 'full_timeout':
                    assert frames[0]['data'] == 'STREAM_BACKPRESSURE_TIMEOUT'
            assert producer[0].done()
        case.lease.fence.finish.assert_not_awaited()
        case.lease.release.assert_awaited_once()
        reset.assert_called_once()
        assert context.get() is None
        assert case.chat._update_session_status.await_args.args[1] == (
            'failed' if kind == 'full_timeout' else 'cancelled')
        assert isinstance(case.audit.log.await_args.kwargs['latency_ms'], int)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['event', 'final'])
async def test_api_oversized_payload_never_commits_success(kind: str) -> None:
    async with chat_fixture() as case:
        stopped = asyncio.Event()
        original = case.run_graph_stream
        async def graph(*args: Any, **kwargs: Any) -> AsyncIterator[dict]:
            try:
                async for frame in original(*args, **kwargs):
                    if kind == 'event':
                        yield event('x' * 100000)
                    else:
                        yield frame
                case.checkpoints['session-a']['final_answer'] = 'x' * 100000
            finally:
                stopped.set()
        with patch.object(sys.modules['app.graph.graph'], 'run_graph_stream', graph):
            response = await case.call('stream', case.owner)
            frames = [parse(f) async for f in response.events]
        assert frames[-1] == {'type': 'error', 'data': 'STREAM_EVENT_TOO_LARGE'}
        assert all(f['type'] != 'final' for f in frames)
        assert stopped.is_set()
        case.lease.fence.finish.assert_not_awaited()
        case.lease.release.assert_awaited_once()
        assert case.chat._update_session_status.await_args.args[1] == 'failed'


@pytest.mark.asyncio
async def test_unstarted_response_close_releases_lease_without_graph() -> None:
    async with chat_fixture() as case:
        response = await case.call('stream', case.owner)
        assert case.stream_calls == []
        await response.close()
        await response.close()
        assert case.stream_calls == []
        case.lease.release.assert_awaited_once()
        assert case.chat._update_session_status.await_args.args[1] == 'cancelled'
        assert [item async for item in response.events] == []


@pytest.mark.asyncio
async def test_disconnect_before_scheduled_producer_starts_releases_lease() -> None:
    async with chat_fixture() as case:
        response = await case.call('stream', case.owner)
        first = asyncio.create_task(anext(response.events))
        # The iterator schedules produce(), but this task resumes before it starts.
        await asyncio.sleep(0)
        await response.close()
        with pytest.raises(StopAsyncIteration):
            await first
        assert case.stream_calls == []
        case.lease.release.assert_awaited_once()
        assert case.chat._update_session_status.await_args.args[1] == 'cancelled'


@pytest.mark.asyncio
@pytest.mark.parametrize('failing_cleanup', ['status', 'audit', 'release'])
async def test_error_cleanup_failure_still_terminates_and_resets_prompt(failing_cleanup: str) -> None:
    async with chat_fixture() as case:
        reset = Mock()
        case.chat.reset_prompt_user = reset
        if failing_cleanup == 'status':
            case.chat._update_session_status.side_effect = RuntimeError('PRIVATE')
        elif failing_cleanup == 'release':
            case.lease.release.side_effect = RuntimeError('PRIVATE')
        async def graph(*args: Any, **kwargs: Any) -> AsyncIterator[dict]:
            yield event('x' * 100000)
        with patch.object(sys.modules['app.graph.graph'], 'run_graph_stream', graph):
            response = await case.call('stream', case.owner)
            if failing_cleanup == 'audit':
                case.audit.log.side_effect = RuntimeError('PRIVATE')
            frames = [parse(f) async for f in response.events]
        assert frames[-1] == {'type': 'error', 'data': 'STREAM_EVENT_TOO_LARGE'}
        case.lease.release.assert_awaited_once()
        reset.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('slow_cleanup', ['status', 'audit', 'release'])
async def test_cleanup_timeout_still_attempts_release_and_resets_context(
        monkeypatch: pytest.MonkeyPatch, slow_cleanup: str) -> None:
    monkeypatch.setattr(stream, 'CLEANUP_SECONDS', .02)
    async with chat_fixture() as case:
        reset = Mock()
        case.chat.reset_prompt_user = reset
        async def slow(**kwargs: Any) -> None:
            await asyncio.Event().wait()
        async def graph(*args: Any, **kwargs: Any) -> AsyncIterator[dict]:
            yield event('x' * 100000)
        with patch.object(sys.modules['app.graph.graph'], 'run_graph_stream', graph):
            response = await case.call('stream', case.owner)
            target = {'status': case.chat._update_session_status,
                      'audit': case.audit.log, 'release': case.lease.release}[slow_cleanup]
            # AsyncMock supplies positional status arguments as well.
            async def blocked(*args: Any, **kwargs: Any) -> None:
                await slow()
            target.side_effect = blocked
            async def consume() -> list[dict]:
                return [parse(f) async for f in response.events]
            frames = await asyncio.wait_for(consume(), 1)
        assert frames[-1]['type'] == 'error'
        case.lease.release.assert_awaited()
        reset.assert_called_once()


@pytest.mark.asyncio
async def test_stuck_generator_cleanup_revokes_lease_and_observes_late_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stream, 'CLEANUP_SECONDS', .02)
    async with chat_fixture() as case:
        stuck, unblock = asyncio.Event(), asyncio.Event()
        producer = []
        reset = Mock()
        case.chat.reset_prompt_user = reset
        async def graph(*args: Any, **kwargs: Any) -> AsyncIterator[dict]:
            producer.append(asyncio.current_task())
            try:
                yield event()
                await asyncio.Event().wait()
            finally:
                stuck.set()
                while not unblock.is_set():
                    try:
                        await unblock.wait()
                    except asyncio.CancelledError:
                        continue
        with patch.object(sys.modules['app.graph.graph'], 'run_graph_stream', graph):
            response = await case.call('stream', case.owner)
            await anext(response.events)
            try:
                await asyncio.wait_for(response.events.aclose(), 1)
                assert stuck.is_set() and producer[0] in stream._pending
                case.lease.release.assert_awaited_once()
                reset.assert_not_called()
                case.lease.fence.finish.assert_not_awaited()
            finally:
                unblock.set()
                await asyncio.wait_for(producer[0], 1)
        reset.assert_called_once()
        await asyncio.sleep(0)
        assert producer[0] not in stream._pending


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['audit', 'disconnect', 'watch_exit'])
async def test_post_publication_delivery_failure_never_downgrades_completed_state(fault: str) -> None:
    async with chat_fixture() as case:
        if fault == 'watch_exit':
            @asynccontextmanager
            async def watch(**kwargs: Any) -> AsyncIterator[None]:
                yield
                raise RuntimeError('PRIVATE')
            case.lease.watch = watch
        response = await case.call('stream', case.owner)
        if fault == 'audit':
            case.audit.log.side_effect = RuntimeError('PRIVATE')
        frames = []
        while True:
            frame = parse(await anext(response.events))
            frames.append(frame)
            if frame['type'] == 'final':
                break
        assert case.lease.fence.finish.await_args.args == ('completed',)
        await response.events.aclose()
        case.chat._update_session_status.assert_not_awaited()
        case.lease.release.assert_awaited_once()
        assert sum(f['type'] == 'final' for f in frames) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('version', ['2.0', '2.4'])
@pytest.mark.parametrize('phase', ['headers', 'body'])
async def test_real_response_drives_api_cleanup_on_send_timeout(monkeypatch: pytest.MonkeyPatch, phase: str, version: str) -> None:
    monkeypatch.setattr(sse_response, 'SEND_TIMEOUT_SECONDS', .02)
    async with chat_fixture() as case:
        async def graph(*args: Any, **kwargs: Any) -> AsyncIterator[dict]:
            yield event()
            await asyncio.Event().wait()
        with patch.object(sys.modules['app.graph.graph'], 'run_graph_stream', graph), \
                patch.object(sys.modules['app.api.sse_response'], 'BoundedStreamingResponse',
                             sse_response.BoundedStreamingResponse):
            response = await case.call('stream', case.owner)
        async def receive() -> dict:
            await asyncio.Event().wait()
        async def send(message: dict) -> None:
            if message['type'] == ('http.response.start' if phase == 'headers'
                                   else 'http.response.body'):
                await asyncio.Event().wait()
        await asyncio.wait_for(response({'type': 'http', 'asgi': {'spec_version': version}},
                                       receive, send), 1)
        case.lease.release.assert_awaited_once()
        case.lease.fence.finish.assert_not_awaited()
        assert case.chat._update_session_status.await_args.args[1] == 'cancelled'
