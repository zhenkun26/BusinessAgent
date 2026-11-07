"""Read-only snapshots around externally coordinated isolated PG restart."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
x = json.loads((Path(os.environ['C10_CONFIG_PATH'])).read_text())
for key in ['host', 'port', 'user', 'password']:
    os.environ['POSTGRES_' + key.upper()] = str(x['pg_' + key])
os.environ.update(POSTGRES_DB=x['c10_database'], CHECKPOINT_BACKEND='postgres',
                  APP_ENV='dev', TELEMETRY_MODE='disabled', OTEL_ENABLED='false')
spec = importlib.util.spec_from_file_location('prior', HERE / 'baseline.py')
prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)


def binding():
    out = prior.binding()
    out['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return out


async def main():
    from app.core.database import init_db, close_db, get_session_factory
    from app.core.session_fencing import publications
    from app.graph.checkpointer import get_checkpointer, reset_checkpointer
    from sqlalchemy import text
    phase, source = sys.argv[1:3]
    evidence = json.loads(Path(source).read_text())
    configs = evidence['scenarios'] if phase == 'before' else evidence['targets']
    result = {'phase': phase, 'source': source, 'pid': os.getpid(), 'before': binding(),
              'checks': [], 'targets': configs, 'status': 'RUNNING'}
    try:
        await init_db()
        saver, backend = await get_checkpointer()
        snapshots = []
        async with get_session_factory()() as db:
            row = (await db.execute(text('SELECT version() AS version, pg_postmaster_start_time()::text AS started'))).mappings().one()
            result['server'] = dict(row)
        for target in configs:
            async with get_session_factory()() as db:
                row = (await db.execute(text('SELECT s.status,s.token_count,f.owner_token::text AS owner FROM sessions s LEFT JOIN session_write_fences f USING(session_id) WHERE session_id=:sid'), {'sid': target['session']})).mappings().one()
            value = await saver.aget_tuple(target['config'])
            assert value is not None
            snapshots.append({'session': target['session'], 'metadata': dict(row),
                'publications': await publications(target['session']),
                'checkpoint': value.checkpoint, 'pending_writes': value.pending_writes})
        # Normalize JSON tuple/list representations before comparison.
        result['snapshots'] = json.loads(json.dumps(snapshots))
        if phase == 'after':
            checks = [
                ('fresh_reader_process', result['pid'] != evidence['pid']),
                ('postgres_actually_restarted', result['server']['started'] != evidence['server']['started']),
                ('postgres_version_unchanged', result['server']['version'] == evidence['server']['version']),
                ('exact_ids_pending_writes_pointer_status_tokens_survived', result['snapshots'] == evidence['snapshots']),
                ('source_harness_unchanged_across_restart', result['before'] == evidence['before']),
            ]
            result['checks'] = [{'name': n, 'pass': b} for n, b in checks]
            assert all(b for n, b in checks), 'restart check failed'
        result['status'] = 'PASS'
    except Exception as exc:
        result['status'] = 'FAIL'
        result['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        await reset_checkpointer(); await close_db()
        result['after'] = binding()
        if result['before'] != result['after']:
            result['status'] = 'FAIL'
        output = Path(os.environ['C10_EVIDENCE_DIR']) / ('restart-' + phase + '-' + uuid.uuid4().hex + '.json')
        output.write_text(json.dumps(result, indent=2))
        print(json.dumps({'status': result['status'], 'receipt': str(output), 'snapshot_count': len(result.get('snapshots', [])), 'checks': result['checks'], 'failure': result.get('failure')}))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
