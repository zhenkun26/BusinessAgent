"""NOT RUN until supplied an explicitly isolated fixture environment.

Two independent workers, actual selected PG/Redis saver and PG publication SQL.
No models, HTTP API, fault injection, deletion, or mock stores.
Run from an empty working directory with explicitly supplied POSTGRES_*/REDIS_*.
"""
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


async def worker():
    from app.core.database import init_db, close_db, get_session_factory
    from app.core.cancellation import reserve_session, SessionBusy
    from app.core.runtime_state import runtime_client
    from app.core.session_fencing import publications
    from app.graph.checkpointer import get_checkpointer, reset_checkpointer
    from langgraph.checkpoint.base import empty_checkpoint
    from sqlalchemy import text
    await init_db()
    saver, backend = await get_checkpointer()
    leases, configs = {}, {}
    print(json.dumps({'ready': True, 'pid': os.getpid(), 'backend': backend}), flush=True)
    try:
        for line in sys.stdin:
            arg = json.loads(line)
            op, sid = arg['op'], arg.get('sid')
            result = None
            try:
                if op == 'quit':
                    break
                if op == 'reserve':
                    try:
                        leases[sid] = await reserve_session(sid)
                        result = {'token': leases[sid].token, 'thread': leases[sid].fence.thread_id}
                    except SessionBusy:
                        result = {'busy': True}
                elif op == 'write':
                    cp = empty_checkpoint()
                    cp['channel_values'] = {'answer': arg['answer']}
                    cp['channel_versions'] = {'answer': '1'}
                    configs[sid] = await saver.aput(leases[sid].fence.config, cp,
                                                   {'source': 'input', 'step': 0, 'parents': {}},
                                                   {'answer': '1'})
                    await saver.aput_writes(configs[sid], [('audit', arg['answer'])], 'synthetic-task')
                    result = configs[sid]
                elif op == 'read':
                    value = await saver.aget_tuple(arg['config'])
                    result = None if value is None else {'checkpoint': value.checkpoint,
                                                         'pending_writes': value.pending_writes}
                elif op == 'finish':
                    lease = leases[sid]
                    result = await lease.fence.finish('completed', tokens=arg['tokens'], publication={
                        'backend': backend, 'thread_id': lease.fence.thread_id,
                        'checkpoint_ns': '', 'checkpoint_id': configs[sid]['configurable']['checkpoint_id']})
                elif op == 'renew':
                    result = await leases[sid].fence.renew()
                elif op == 'release':
                    await leases[sid].release()
                    result = True
                elif op == 'snapshot':
                    async with get_session_factory()() as db:
                        row = (await db.execute(text('SELECT s.status, s.token_count, f.owner_token::text AS owner FROM sessions s LEFT JOIN session_write_fences f USING(session_id) WHERE s.session_id=:sid'), {'sid': sid})).mappings().one()
                        result = dict(row)
                    result['publications'] = await publications(sid)
                    async with runtime_client() as client:
                        from app.core.runtime_state import state_key
                        result['redis_owner'] = await client.get(state_key('run', sid))
                print(json.dumps({'ok': True, 'result': result}), flush=True)
            except Exception as exc:
                print(json.dumps({'ok': False, 'error': type(exc).__name__, 'code': str(exc)}), flush=True)
    finally:
        await reset_checkpointer()
        await close_db()


def binding():
    repo = ROOT.parent
    files = ['app/core/session_fencing.py', 'app/core/cancellation.py', 'app/core/database.py',
             'app/core/runtime_state.py', 'app/graph/checkpointer.py']
    files += [str(p.relative_to(ROOT)) for p in Path(__file__).parent.glob('*.py')]
    return {'head': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
            'status': subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True),
            'sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}}


def main():
    assert os.environ.get('C10_ISOLATED_FIXTURE') == 'confirmed', 'Explicit isolated fixture required'
    assert os.environ.get('CHECKPOINT_BACKEND') in {'postgres', 'redis'}
    for name in ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER',
                 'POSTGRES_PASSWORD', 'REDIS_HOST', 'REDIS_PORT', 'REDIS_PASSWORD']:
        assert name in os.environ, name
    report = {'scope': 'actual selected saver + PostgreSQL fence + Redis lease; direct-store, not API/model E2E',
              'backend': os.environ['CHECKPOINT_BACKEND'],
              'before': binding(), 'versions': {}, 'checks': [], 'status': 'RUNNING'}
    for package in ['SQLAlchemy', 'asyncpg', 'psycopg', 'langgraph-checkpoint-postgres', 'langgraph-checkpoint-redis', 'langgraph-checkpoint', 'redis']:
        report['versions'][package] = importlib.metadata.version(package)
    report['python'] = sys.version
    processes = []
    def receive(proc):
        assert select.select([proc.stdout], [], [], 25)[0], 'worker response timeout'
        line = proc.stdout.readline()
        assert line, 'worker exited'
        return json.loads(line)
    def call(proc, op, sid=None, **kwargs):
        proc.stdin.write(json.dumps(dict(op=op, sid=sid, **kwargs)) + '\n')
        proc.stdin.flush()
        data = receive(proc)
        assert data.get('ok'), data
        return data['result']
    def check(name, condition):
        report['checks'].append({'name': name, 'pass': bool(condition)})
        assert condition, name
    try:
        # Provisioning is deliberately external; these are only synthetic data rows.
        import psycopg
        conn = psycopg.connect(host=os.environ['POSTGRES_HOST'], port=os.environ['POSTGRES_PORT'],
            dbname=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'],
            password=os.environ['POSTGRES_PASSWORD'], connect_timeout=5)
        suffix = uuid.uuid4().hex
        sid, other, uid = 'c10-' + suffix, 'c10-other-' + suffix, 'c10-user-' + suffix
        with conn:
            report['postgres_version'] = conn.execute('SELECT version()').fetchone()[0]
            conn.execute('INSERT INTO users(user_id,username,role,password_hash) VALUES(%s,%s,%s,%s)',
                         (uid, 'Synthetic C10 ' + suffix, 'admin', 'not-a-login-password'))
            for session in (sid, other):
                conn.execute('INSERT INTO sessions(session_id,user_id,status) VALUES(%s,%s,%s)', (session, uid, 'running'))
        report['synthetic_sessions'] = [sid, other]
        for _ in range(2):
            proc = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--worker'],
                cwd=os.environ['C10_EVIDENCE_DIR'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
            processes.append(proc)
            check('worker_' + str(_) + '_real_backend_ready', receive(proc).get('backend') == os.environ['CHECKPOINT_BACKEND'])
        a, b = processes
        report['pids'] = [p.pid for p in processes]
        check('independent_pids', a.pid != b.pid)
        old = call(a, 'reserve', sid)
        old_config = call(a, 'write', sid, answer='synthetic old orphan')
        check('active_overlap_refused', call(b, 'reserve', sid) == {'busy': True})
        foreign = call(b, 'reserve', other)
        foreign_config = call(b, 'write', other, answer='synthetic independent session')
        check('cross_session_thread_isolated', foreign['thread'] != old['thread'])
        check('independent_session_published', call(b, 'finish', other, tokens=7))
        # Natural DB-clock and Redis expiry. Do not patch clocks or mutate lease timestamps.
        time.sleep(31)
        check('expired_owner_cannot_renew', call(a, 'renew', sid) is False)
        successor = call(b, 'reserve', sid)
        check('successor_new_thread_token', successor['token'] != old['token'] and successor['thread'] != old['thread'])
        successor_config = call(b, 'write', sid, answer='synthetic accepted successor')
        before = call(b, 'snapshot', sid)
        check('expired_owner_publish_rejected', call(a, 'finish', sid, tokens=999) is False)
        call(a, 'release', sid)
        after = call(b, 'snapshot', sid)
        check('stale_release_preserves_successor_redis_pg', before == after and after['redis_owner'] == successor['token'] and after['owner'].replace('-', '') == successor['token'])
        check('successor_publication_commits', call(b, 'finish', sid, tokens=11))
        accepted = call(b, 'snapshot', sid)
        check('pointer_terminal_tokens_owner_consistent', accepted['status'] == 'completed' and accepted['token_count'] == 11 and accepted['owner'] is None and len(accepted['publications']) == 1 and accepted['publications'][0]['checkpoint_id'] == successor_config['configurable']['checkpoint_id'])
        check('duplicate_publish_rejected', call(b, 'finish', sid, tokens=11) is False)
        # Late raw orphan writes are permitted; they must not alter accepted publication.
        late_config = call(a, 'write', sid, answer='synthetic late orphan write')
        check('late_raw_aput_and_aput_writes_do_not_publish', call(b, 'snapshot', sid) == accepted)
        readback = call(a, 'read', config=successor_config)
        check('cross_process_exact_id_read', readback['checkpoint']['channel_values']['answer'] == 'synthetic accepted successor')
        check('pending_writes_real_roundtrip', any(item[1:] == ['audit', 'synthetic accepted successor'] for item in readback['pending_writes']))
        other_state = call(a, 'snapshot', other)
        check('other_session_unchanged', other_state['status'] == 'completed' and other_state['token_count'] == 7 and other_state['publications'][0]['checkpoint_id'] == foreign_config['configurable']['checkpoint_id'])
        report['final_state'] = accepted
        report['status'] = 'PASS'
    except Exception as exc:
        report['status'] = 'FAIL'
        report['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        for proc in processes:
            if proc.poll() is None:
                try:
                    proc.stdin.write('{"op":"quit"}\n'); proc.stdin.flush(); proc.wait(timeout=15)
                except Exception:
                    proc.terminate(); proc.wait(timeout=5)
        report['after'] = binding()
        if report['before'] != report['after']:
            report['status'] = 'FAIL'
            report['source_binding_changed'] = True
        report['check_count'] = len(report['checks'])
        report['failed_count'] = sum(not x['pass'] for x in report['checks'])
        print(json.dumps(report, indent=2, default=str))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    if '--worker' in sys.argv:
        asyncio.run(worker())
    else:
        raise SystemExit(main())
