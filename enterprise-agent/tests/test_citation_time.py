"""F2-08: actual source construction with synthetic retrieval and generation only."""
from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
from typing import Any, Optional
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
ZONES = ('UTC', 'America/New_York', 'Asia/Shanghai')


@contextmanager
def server_zone(zone: str) -> Iterator[None]:
    """Change libc's zone for one serial test; restore the caller's setting."""
    try:
        with patch.dict(os.environ, {'TZ': zone}):
            time.tzset()
            yield
    finally:
        time.tzset()


class CitationTimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        tree = ast.parse((ROOT / 'app/agents/knowledge.py').read_text())
        models = [n for n in tree.body if isinstance(n, ast.ClassDef)
                  and n.name in {'RetrievalSource', 'AgentResult'}]
        imports = [n for n in tree.body if isinstance(n, ast.ImportFrom)
                   and n.module == 'datetime']
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'KnowledgeAgent')
        run = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef)
                   and n.name == 'run')
        self.ns = dict(BaseModel=BaseModel, Field=Field, Optional=Optional, time=time,
                       __name__='citation_time_fixture', logger=Mock(),
                       resolve_scope=lambda *args: SimpleNamespace(allows_result=lambda r: True),
                       Coverage=SimpleNamespace(NONE=SimpleNamespace(value='none'),
                                                PARTIAL=SimpleNamespace(value='partial')),
                       ConfidenceDecider=SimpleNamespace(detect_scene=lambda q: 'general',
                                                        combine_score=lambda **kw: .9))
        exec(compile(ast.Module(body=[*imports, *models, run], type_ignores=[]),
                     'app/agents/knowledge.py', 'exec', dont_inherit=True), self.ns)
        decision = SimpleNamespace(coverage=SimpleNamespace(value='full'),
                                   threshold_used=.7, reason='synthetic')
        self.owner = SimpleNamespace(
            user_role='salesperson', user_dept='sales', rerank_top_k=5,
            degradation_chain=SimpleNamespace(run=AsyncMock()),
            _generate_answer=AsyncMock(return_value=('Synthetic answer', .9)),
            decider=SimpleNamespace(decide=lambda **kw: decision),
            _apply_decision=lambda answer, decision: (answer, ''))
        doubles = {}
        for name, members in {
            'app.graph.history': {'expand_query_with_history': lambda q, h: q},
            'app.observability.token_usage': {'snapshot_total_tokens': lambda: 0},
            'app.core.execution_budget': {'check_execution_budget': lambda: None},
        }.items():
            module = ModuleType(name)
            module.__dict__.update(members)
            doubles[name] = module
        self.modules = patch.dict(sys.modules, doubles)
        self.modules.start()
        self.addCleanup(self.modules.stop)

    async def generate(self, *epochs: object) -> Any:
        self.owner.degradation_chain.run.return_value = SimpleNamespace(
            results=[SimpleNamespace(document_id='synthetic', chunk_id=str(i), title='Fixture',
                                     source_url='', updated_at=value, score=.9,
                                     dept_namespace='sales') for i, value in enumerate(epochs)],
            stage='vector', error=None)
        return await self.ns['run'](self.owner, 'Synthetic query')

    async def test_new_citations_are_utc_across_host_zones_and_dst(self) -> None:
        # UTC midnight, both sides of US DST changes, and fractional/epoch-zero values.
        instants = ['2026-10-20T00:15:00+00:00', '2026-03-08T06:59:59+00:00',
                    '2026-03-08T07:00:00+00:00', '2026-11-01T05:59:59+00:00',
                    '2026-11-01T06:00:00+00:00', '1970-01-01T00:00:00+00:00',
                    '2026-10-20T00:15:00.125000+00:00']
        for zone in ZONES:
            with server_zone(zone):
                for text in instants:
                    with self.subTest(zone=zone, instant=text):
                        expected = datetime.fromisoformat(text)
                        result = await self.generate(expected.timestamp())
                        self.assertTrue(result.success)
                        value = result.sources[0].updated_at
                        self.assertEqual(value.tzinfo, timezone.utc)
                        self.assertEqual(value, expected)
                        wire = json.loads(result.model_dump_json())['sources'][0]['updated_at']
                        self.assertTrue(wire.endswith(('Z', '+00:00')))
                        self.assertEqual(datetime.fromisoformat(wire.replace('Z', '+00:00')),
                                         expected)

    async def test_invalid_epochs_fail_without_partial_success(self) -> None:
        for zone in ZONES:
            with server_zone(zone):
                for value in (None, 'invalid', float('nan'), float('inf'), -float('inf'), 1e30):
                    with self.subTest(zone=zone, epoch=repr(value)):
                        result = await self.generate(0, value)
                        self.assertFalse(result.success)
                        self.assertEqual(result.error, 'KNOWLEDGE_SERVICE_FAILED')
                        self.assertEqual(result.sources, [])

    async def test_empty_retrieval_does_not_generate_or_invent_citation_time(self) -> None:
        result = await self.generate()
        self.assertFalse(result.success)
        self.assertEqual(result.sources, [])
        self.owner._generate_answer.assert_not_awaited()
