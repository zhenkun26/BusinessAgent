"""Request-local, fail-closed publication eligibility before reranking and generation."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator

from sqlalchemy import text

from app.core.knowledge_publication import snapshot
from app.security.retrieval_policy import RetrievalAccessError

_current: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar('publication_visibility', default=None)
MATCH = ('document_id', 'title', 'content', 'dept_namespace', 'doc_type', 'source_url',
         'access_roles', 'is_active')


def visible_results(results: list[Any]) -> list[Any]:
    current = _current.get()
    if current is None:
        raise RetrievalAccessError('KNOWLEDGE_VISIBILITY_REQUIRED')
    output = []
    seen = set()
    for result in results:
        cid = getattr(result, 'chunk_id', None)
        expected = current.get(cid)
        if (expected is not None and cid not in seen
                and all(getattr(result, key, None) == expected[key] for key in MATCH)):
            output.append(result)
            seen.add(cid)
    return output


@asynccontextmanager
async def publication_scope(scope: Any) -> AsyncIterator[None]:
    from app.core.database import get_session_factory
    try:
        async with asyncio.timeout(10), get_session_factory()() as db:
            rows = (await db.execute(text("""SELECT d.*, p.snapshot AS published_snapshot, p.chunks
                FROM documents d JOIN knowledge_publications p
                  ON p.publication_id = d.active_publication AND p.document_id = d.document_id
                WHERE d.status = 'active' AND p.state = 'published'
                  AND d.pending_publication IS NULL
                  AND (:all_namespaces OR d.dept_namespace IN (
                      SELECT jsonb_array_elements_text(CAST(:namespaces AS JSONB))))
                  AND d.access_roles @> CAST(:role AS JSONB)
                  AND (:all_types OR d.doc_type IN (
                      SELECT jsonb_array_elements_text(CAST(:types AS JSONB))))
                ORDER BY d.document_id LIMIT 1001"""), {
                    'all_namespaces': scope.namespaces is None,
                    'namespaces': json.dumps(scope.namespaces or []),
                    'role': json.dumps([scope.role]), 'all_types': scope.doc_types is None,
                    'types': json.dumps(scope.doc_types or []),
                })).mappings().all()
        if len(rows) > 1000:
            raise ValueError
        visible = {}
        for row in rows:
            data = snapshot(row)
            if data != row['published_snapshot'] or not scope.allows(
                    data['dept_namespace'], data['access_roles'], True, data['doc_type']):
                continue
            chunks = row['chunks']
            if not isinstance(chunks, list) or not chunks or len(chunks) > 1000:
                raise ValueError
            for chunk in chunks:
                if (chunk['document_id'] != data['document_id'] or chunk['is_active'] is not True
                        or any(chunk[k] != data[k] for k in ('title', 'dept_namespace',
                                                          'doc_type', 'source_url', 'access_roles'))
                        or chunk['chunk_id'] in visible):
                    raise ValueError
                visible[chunk['chunk_id']] = chunk
            if len(visible) > 10000:
                raise ValueError
    except Exception:
        raise RetrievalAccessError('KNOWLEDGE_VISIBILITY_UNAVAILABLE') from None
    token = _current.set(visible)
    try:
        yield
    finally:
        _current.reset(token)
