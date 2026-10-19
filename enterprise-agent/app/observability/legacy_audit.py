"""Explicit reviewed-copy import; never reads legacy JSON during normal application startup."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

from app.security.redaction import redact_value
from app.observability.retained import RetainedStore


def record_from_legacy(filename: str, raw: bytes, expected_sha256: str) -> dict[str, Any]:
    if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('LEGACY_AUDIT_HASH_REJECTED')
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get('event_type'), str):
        raise ValueError('LEGACY_AUDIT_RECORD_REJECTED')
    timestamp = datetime.fromisoformat(value['timestamp'])
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    record = {key: value.get(key) for key in (
        'event_type','session_id','user_id','tool_name','input_summary','output_summary',
        'success','latency_ms','payload')}
    record.update(event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
        'businessagent:c21:legacy:'+filename+':'+expected_sha256)),
        occurred_at=timestamp.isoformat(), request_id=None, trace_id=None, task_id=None)
    record = redact_value(record)
    for key in ('input_summary','output_summary'):
        record[key] = str(record[key] or '')[:500]
    return record


def import_review(source: Path, manifest: Path, store: RetainedStore | None = None) -> int:
    if (any(p.is_symlink() for p in (source, *source.parents, manifest, *manifest.parents))
            or manifest.stat().st_size > 262144):
        raise ValueError('LEGACY_AUDIT_PATH_REJECTED')
    decisions = json.loads(manifest.read_text())
    if not isinstance(decisions, list) or len(decisions) > 1000:
        raise ValueError('LEGACY_AUDIT_REVIEW_REJECTED')
    records = []; seen = set()
    for item in decisions:
        filename = item['file']
        if (not isinstance(filename, str) or Path(filename).name != filename
                or not filename.endswith('.json') or filename in seen
                or item['decision'] not in {'import_new', 'already_in_database'}):
            raise ValueError('LEGACY_AUDIT_REVIEW_REJECTED')
        seen.add(filename)
        path = source / filename
        if path.is_symlink() or path.stat().st_size > 262144:
            raise ValueError('LEGACY_AUDIT_PATH_REJECTED')
        record = record_from_legacy(filename, path.read_bytes(), item['sha256'])
        if item['decision'] == 'import_new': records.append(record)
    # Complete validation before any new outbox writes. Retries have stable IDs.
    if store is not None:
        for record in records: store.append('audit', record['event_id'], record)
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--apply-to-retained-store', type=Path)
    args = parser.parse_args()
    try:
        store = RetainedStore(str(args.apply_to_retained_store)) if args.apply_to_retained_store else None
        count = import_review(args.source, args.review, store)
        print(json.dumps({'status': 'RETAINED' if store else 'PLAN_ONLY', 'import_new': count,
                          'runtime_acceptance': 'BLOCKED'}))
        return 0
    except Exception:
        print('LEGACY_AUDIT_REVIEW_FAILED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
