"""Transactional knowledge approval and frozen publication handoff."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.task_queue import TaskRejected, enqueue_task
from app.core.tool_operations import canonical, fingerprint

NAMESPACES = frozenset({
    "dept_sales", "dept_finance", "dept_cs", "dept_hr", "shared_company", "restricted_exec",
})
ROLES = frozenset({"salesperson", "customer_service", "finance", "manager", "admin"})
DOCUMENT_SQL = """SELECT document_id, title, content, doc_type, dept_namespace,
    access_roles, uploaded_by, status, source_url, reviewed_by FROM documents WHERE document_id = :did"""


def document_snapshot(row: Any) -> dict[str, Any]:
    roles = row["access_roles"]
    if (not isinstance(roles, list) or not roles or len(roles) > 20
            or any(not isinstance(role, str) or role not in ROLES for role in roles)):
        raise TaskRejected("TASK_INPUT_INVALID")
    snapshot = {key: row[key] for key in (
        "document_id", "title", "content", "access_roles", "uploaded_by",
    )}
    snapshot["content"] = row["content"] or row["title"]
    return snapshot


def publication_options(doc_type: str, dept_namespace: str) -> dict[str, str]:
    if (not isinstance(doc_type, str) or not 1 <= len(doc_type) <= 32
            or not isinstance(dept_namespace, str) or dept_namespace not in NAMESPACES):
        raise TaskRejected("TASK_INPUT_INVALID")
    return {"doc_type": doc_type, "dept_namespace": dept_namespace}


async def queue_knowledge_approval(session: Any, document_id: str, reviewer: str,
                                   doc_type: str, dept_namespace: str) -> dict[str, Any]:
    options = publication_options(doc_type, dept_namespace)
    if not isinstance(document_id, str) or not 1 <= len(document_id) <= 64:
        raise TaskRejected("TASK_INPUT_INVALID")
    row = (await session.execute(text(DOCUMENT_SQL + " FOR UPDATE"),
                                 {"did": document_id})).mappings().first()
    if row is None:
        raise TaskRejected("TASK_INPUT_INVALID")
    scope = "knowledge:" + document_id
    existing = (await session.execute(text("SELECT * FROM task_jobs WHERE scope_key = :scope"),
                                      {"scope": scope})).mappings().first()
    if existing is not None:
        payload = existing["payload"]
        if (existing["queue_name"] != "tasks:doc_ingest"
                or payload.get("options") != options or payload.get("document_id") != document_id):
            raise TaskRejected("TASK_DOCUMENT_CHANGED")
        return dict(existing)
    if row["status"] != "draft":
        raise TaskRejected("TASK_DOCUMENT_CHANGED")
    job = await enqueue_task(session, "tasks:doc_ingest", scope, {
        "document_id": document_id, "reviewer": reviewer, "options": options,
        "snapshot_hash": fingerprint(document_snapshot(row)),
    })
    await session.execute(text("""UPDATE documents SET status = 'queued', reviewed_by = :reviewer,
        reviewed_at = CURRENT_TIMESTAMP, ingest_error = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE document_id = :did AND status = 'draft'"""),
        {"did": document_id, "reviewer": reviewer})
    # Acceptance audit shares the transaction; it does not assert successful publication.
    await session.execute(text("""INSERT INTO audit_logs
        (event_type, user_id, output_summary, success, payload)
        VALUES ('knowledge_publication_queued', :reviewer, 'Publication queued', true,
                CAST(:payload AS JSONB))"""), {
            "reviewer": reviewer,
            "payload": canonical({"task_id": str(job["task_id"]),
                                  "document_id": document_id, "phase": "queued"}),
        })
    return job


async def handle_knowledge_job(payload: dict[str, Any]) -> None:
    from app.core.database import get_session_factory
    from app.rag.ingest import MilvusIngestService
    from app.security.rbac import AgentRole, resolve_active_user

    if (set(payload) != {"document_id", "reviewer", "options", "snapshot_hash"}
            or not isinstance(payload["document_id"], str)
            or not isinstance(payload["options"], dict)
            or set(payload["options"]) != {"doc_type", "dept_namespace"}):
        raise TaskRejected("TASK_INPUT_INVALID")
    options = publication_options(**payload["options"])
    async with get_session_factory()() as session:
        try:
            user = await resolve_active_user(payload["reviewer"], session)
            if user.role != AgentRole.ADMIN:
                raise TaskRejected("TASK_AUTHORIZATION_DENIED")
        except Exception:
            raise TaskRejected("TASK_AUTHORIZATION_DENIED") from None
        row = (await session.execute(text(DOCUMENT_SQL),
                                     {"did": payload["document_id"]})).mappings().first()
        if (row is None or row["status"] not in {"queued", "indexing", "active"}
                or fingerprint(document_snapshot(row)) != payload["snapshot_hash"]):
            raise TaskRejected("TASK_DOCUMENT_CHANGED")
        snapshot = document_snapshot(row)
    count = await MilvusIngestService().ingest_text(
        document_id=snapshot["document_id"], title=snapshot["title"],
        content=snapshot["content"] or snapshot["title"],
        access_roles=snapshot["access_roles"], uploaded_by=snapshot["uploaded_by"],
        source_url=row.get("source_url"), publication_approval=payload, **options,
    )
    if type(count) is not int or count <= 0:
        raise TaskRejected("TASK_EMPTY_RESULT")


async def retry_knowledge_task(session: Any, task_id: str, actor: str) -> dict[str, Any]:
    """Explicit recovery of a dead knowledge job; never reset queue rows or change input."""
    old = (await session.execute(text("SELECT * FROM task_jobs WHERE task_id = :tid FOR UPDATE"),
                                 {'tid': task_id})).mappings().first()
    if old is None or old['queue_name'] != 'tasks:doc_ingest' or old['state'] != 'dead':
        raise TaskRejected('KNOWLEDGE_RETRY_DENIED')
    payload = old['payload']
    if set(payload) != {'document_id', 'reviewer', 'options', 'snapshot_hash'}:
        raise TaskRejected('KNOWLEDGE_RETRY_DENIED')
    row = (await session.execute(text(DOCUMENT_SQL + ' FOR UPDATE'),
                                 {'did': payload['document_id']})).mappings().first()
    if (row is None or row['status'] not in {'queued', 'indexing', 'active'}
            or fingerprint(document_snapshot(row)) != payload['snapshot_hash']):
        raise TaskRejected('KNOWLEDGE_SOURCE_CHANGED')
    job = await enqueue_task(session, 'tasks:doc_ingest', 'knowledge-retry:' + task_id, payload)
    await session.execute(text("""INSERT INTO audit_logs (event_type, user_id, success, payload)
        VALUES ('knowledge_retry_queued', :uid, true, CAST(:payload AS JSONB))"""),
        {'uid': actor, 'payload': canonical({'previous_task_id': task_id,
            'task_id': str(job['task_id']), 'document_id': payload['document_id']})})
    return job
