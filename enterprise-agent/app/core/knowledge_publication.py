"""Immutable index generations with a PostgreSQL activation boundary; no data deletion."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from sqlalchemy import text

from app.core.knowledge_jobs import document_snapshot, publication_options
from app.core.task_queue import TaskRejected
from app.core.tool_operations import canonical, fingerprint, safe_payload

FIELDS = ('document_id', 'title', 'content', 'doc_type', 'dept_namespace',
          'access_roles', 'uploaded_by', 'source_url')
DOC = "SELECT * FROM documents WHERE document_id = :did FOR UPDATE"


def snapshot(row: Any) -> dict[str, Any]:
    return {key: row.get(key) or ('' if key == 'source_url' else None) for key in FIELDS}


def validate(data: dict[str, Any], texts: list[str]) -> None:
    publication_options(data['doc_type'], data['dept_namespace'])
    document_snapshot(data)
    for key, limit in (('document_id', 64), ('title', 512), ('content', 200000),
                       ('source_url', 1024)):
        value = data[key]
        if not isinstance(value, str) or len(value.encode('utf-8')) > limit:
            raise TaskRejected('KNOWLEDGE_INPUT_INVALID')
    if not data['document_id'] or not data['content'].strip() or not data['title'].strip():
        raise TaskRejected('KNOWLEDGE_INPUT_INVALID')
    if (not texts or len(texts) > 1000 or any(not isinstance(t, str) or not t.strip()
            or len(t.encode('utf-8')) > 8192 for t in texts)):
        raise TaskRejected('KNOWLEDGE_CHUNKS_INVALID')
    safe_payload(data)


class PublicationStore:
    def __init__(self) -> None:
        from app.core.database import get_session_factory
        self.factory = get_session_factory()

    async def prepare(self, data: dict[str, Any], texts: list[str], recipe: dict[str, Any],
                      approval: dict[str, Any] | None = None) -> dict[str, Any]:
        validate(data, texts)
        digest = fingerprint({'snapshot': data, 'texts': texts, 'recipe': recipe})
        async with asyncio.timeout(10), self.factory() as db:
            # Trusted CLI may create a document; approved jobs must find their original draft.
            if approval is None:
                await db.execute(text("""INSERT INTO documents (document_id, title, status)
                    VALUES (:did, :title, 'importing') ON CONFLICT (document_id) DO NOTHING"""),
                    {'did': data['document_id'], 'title': data['title']})
            row = (await db.execute(text(DOC), {'did': data['document_id']})).mappings().first()
            if row is None:
                raise TaskRejected('KNOWLEDGE_SOURCE_CHANGED')
            if approval is not None:
                if (row['status'] not in {'queued', 'indexing', 'active'}
                        or fingerprint(document_snapshot(row)) != approval['snapshot_hash']):
                    raise TaskRejected('KNOWLEDGE_SOURCE_CHANGED')
                expected = {**document_snapshot(row), **approval['options'],
                            'content': row['content'] or row['title'],
                            'source_url': row.get('source_url') or ''}
                if data != expected or row.get('reviewed_by') != approval['reviewer']:
                    raise TaskRejected('KNOWLEDGE_SOURCE_CHANGED')
            elif row['status'] not in {'importing', 'indexing', 'active'}:
                raise TaskRejected('KNOWLEDGE_STATE_CONFLICT')
            existing = (await db.execute(text("""SELECT * FROM knowledge_publications
                WHERE document_id = :did AND input_hash = :hash"""),
                {'did': data['document_id'], 'hash': digest})).mappings().first()
            if existing is not None:
                pid = str(existing['publication_id'])
                if (row['status'] == 'active' and str(row.get('active_publication')) == pid
                        and existing['state'] == 'published' and snapshot(row) == data):
                    await db.commit()
                    return dict(existing)
                if (row['status'] != 'indexing' or str(row.get('pending_publication')) != pid
                        or fingerprint(snapshot(row)) != existing['source_hash']):
                    raise TaskRejected('KNOWLEDGE_STATE_CONFLICT')
                await db.commit()
                return dict(existing)
            if row['status'] == 'indexing':
                raise TaskRejected('KNOWLEDGE_PUBLICATION_BUSY')
            pid = str(uuid.uuid4())
            chunks = [dict(chunk_id=pid.replace('-', '') + f'_{i:04d}',
                document_id=data['document_id'], title=data['title'], content=body,
                dept_namespace=data['dept_namespace'], doc_type=data['doc_type'],
                source_url=data['source_url'], updated_at=int(time.time()),
                access_roles=data['access_roles'], is_active=True) for i, body in enumerate(texts)]
            record = dict(publication_id=pid, document_id=data['document_id'], input_hash=digest,
                source_hash=fingerprint(snapshot(row)), snapshot=data, chunks=chunks,
                reviewer=approval['reviewer'] if approval else None, state='staging', error_code=None)
            await db.execute(text("""INSERT INTO knowledge_publications
                (publication_id, document_id, input_hash, source_hash, snapshot, chunks, reviewer)
                VALUES (:pid, :did, :hash, :source, CAST(:snapshot AS JSONB),
                        CAST(:chunks AS JSONB), :reviewer)"""), {
                'pid': pid, 'did': data['document_id'], 'hash': digest,
                'source': record['source_hash'], 'snapshot': canonical(data),
                'chunks': canonical(chunks), 'reviewer': record['reviewer']})
            await db.execute(text("""UPDATE documents SET status = 'indexing',
                pending_publication = :pid, ingest_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE document_id = :did"""), {'pid': pid, 'did': data['document_id']})
            await db.commit()  # Unknown commit acknowledgment must not reach vector I/O.
            return record

    async def activate(self, record: dict[str, Any]) -> None:
        async with asyncio.timeout(10), self.factory() as db:
            row = (await db.execute(text(DOC), {'did': record['document_id']})).mappings().first()
            pid = str(record['publication_id'])
            if row is None:
                raise TaskRejected('KNOWLEDGE_SOURCE_CHANGED')
            if (row['status'] == 'active' and str(row.get('active_publication')) == pid
                    and snapshot(row) == record['snapshot']):
                await db.commit()
                return
            if (row['status'] != 'indexing' or str(row.get('pending_publication')) != pid
                    or fingerprint(snapshot(row)) != record['source_hash']):
                raise TaskRejected('KNOWLEDGE_SOURCE_CHANGED')
            if record['reviewer']:
                from app.security.rbac import resolve_active_user
                user = await resolve_active_user(record['reviewer'], db, lock=True)
                if user.role != 'admin':
                    raise TaskRejected('KNOWLEDGE_AUTHORIZATION_DENIED')
            data = record['snapshot']
            await db.execute(text("""UPDATE knowledge_publications SET state = 'published',
                error_code = NULL, published_at = CURRENT_TIMESTAMP WHERE publication_id = :pid"""),
                {'pid': pid})
            activated = (await db.execute(text("""UPDATE documents SET title = :title, content = :content,
                doc_type = :doc_type, dept_namespace = :dept_namespace,
                access_roles = CAST(:roles AS JSONB), source_url = :source_url,
                uploaded_by = :uploaded_by, content_hash = :hash, status = 'active',
                active_publication = :pid, pending_publication = NULL, ingest_error = NULL,
                search_vector = to_tsvector('simple', :content), updated_at = CURRENT_TIMESTAMP
                WHERE document_id = :document_id AND status = 'indexing'
                AND pending_publication = :pid RETURNING document_id"""),
                {**data, 'roles': canonical(data['access_roles']), 'hash': record['input_hash'], 'pid': pid})).fetchone()
            if activated is None:
                raise TaskRejected('KNOWLEDGE_SOURCE_CHANGED')
            await db.execute(text("""INSERT INTO audit_logs (event_type, user_id, success, payload)
                VALUES ('knowledge_published', :uid, true, CAST(:payload AS JSONB))"""), {
                'uid': record['reviewer'], 'payload': canonical({
                    'document_id': record['document_id'], 'publication_id': pid,
                    'chunks': len(record['chunks'])})})
            await db.commit()

    async def failed(self, record: dict[str, Any]) -> None:
        async with asyncio.timeout(10), self.factory() as db:
            await db.execute(text("""UPDATE knowledge_publications SET error_code =
                'KNOWLEDGE_INDEX_UNCONFIRMED' WHERE publication_id = :pid AND state = 'staging'"""),
                {'pid': str(record['publication_id'])})
            await db.execute(text("""UPDATE documents SET ingest_error = 'KNOWLEDGE_INDEX_UNCONFIRMED'
                WHERE document_id = :did AND status = 'indexing' AND pending_publication = :pid"""),
                {'did': record['document_id'], 'pid': str(record['publication_id'])})
            await db.commit()
