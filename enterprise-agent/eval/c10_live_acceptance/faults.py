"""Real-store C10 faults. Hooks schedule SIGSTOP only; never replace store results.
Commit loss uses a TCP proxy dropping PostgreSQL's real COMMIT response.
"""
import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('prior_c10', HERE / 'baseline.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def binding():
    value = prior.binding()
    value['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    value['prior_harness_sha256'] = hashlib.sha256((HERE / 'baseline.py').read_bytes()).hexdigest()
    return value


def worker():
    # Retain the earlier worker verbatim, adding only explicit fault operations.
    source = inspect.getsource(prior.worker)
    source = source.replace("elif op == 'renew':", """elif op == 'fail_callback':
                    result = await leases[sid].fence.finish('failed', error='synthetic lost acknowledgement')
                elif op == 'pause_write':
                    from psycopg import AsyncCursor
                    import signal
                    real_execute, real_many = AsyncCursor.execute, AsyncCursor.executemany
                    target = arg['target']
                    paused = False
                    def maybe_pause(query):
                        nonlocal paused
                        needle = 'INSERT INTO checkpoints' if target == 'aput' else 'INSERT INTO checkpoint_writes'
                        if not paused and needle in str(query):
                            paused = True
                            print(json.dumps({'paused': target, 'pid': os.getpid()}), flush=True)
                            os.kill(os.getpid(), signal.SIGSTOP)
                    async def execute(cursor, query, *args, **kwargs):
                        maybe_pause(query)
                        return await real_execute(cursor, query, *args, **kwargs)
                    async def many(cursor, query, *args, **kwargs):
                        maybe_pause(query)
                        return await real_many(cursor, query, *args, **kwargs)
                    AsyncCursor.execute, AsyncCursor.executemany = execute, many
                    try:
                        if target == 'aput':
                            cp = empty_checkpoint()
                            cp['channel_values'] = {'answer': 'late orphan', 'blob': ['synthetic', 'blob']}
                            cp['channel_versions'] = {'answer': '2', 'blob': '2'}
                            configs[sid] = await saver.aput(leases[sid].fence.config, cp,
                                {'source': 'input', 'step': 1, 'parents': {}}, {'answer': '2', 'blob': '2'})
                        else:
                            await saver.aput_writes(configs[sid], [('audit', 'late orphan')], 'late-synthetic-task')
                        result = {'paused': paused, 'config': configs[sid]}
                    finally:
                        AsyncCursor.execute, AsyncCursor.executemany = real_execute, real_many
                elif op == 'renew':""")
    ns = dict(prior.__dict__)
    exec(compile(source, str(Path(__file__)) + ':worker-extension', 'exec'), ns)
    asyncio.run(ns['worker']())


class CommitProxy:
    """Only plaintext fixture PG. Inspect framed server messages, never credentials."""
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.ready = threading.Event()
        self.dropped = threading.Event()
        self.count = 0
        self.thread = threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True)
        self.thread.start()
        assert self.ready.wait(10)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.server = await asyncio.start_server(self.connection, '127.0.0.1', 0)
        self.listen_port = self.server.sockets[0].getsockname()[1]
        self.stop_event = asyncio.Event()
        self.ready.set()
        await self.stop_event.wait()
        self.server.close()
        await self.server.wait_closed()

    async def connection(self, client_reader, client_writer):
        upstream_reader, upstream_writer = await asyncio.open_connection(self.host, self.port)
        state = {'publication': False, 'tail': b''}
        async def incoming():
            while data := await client_reader.read(65536):
                state['tail'] = (state['tail'] + data)[-65536:]
                if b'INSERT INTO session_checkpoint_publications' in state['tail']:
                    state['publication'] = True
                upstream_writer.write(data)
                await upstream_writer.drain()
        async def outgoing():
            first = True
            while True:
                tag = await upstream_reader.readexactly(1)
                if first and tag == b'N':
                    client_writer.write(tag); await client_writer.drain()
                    first = False
                    continue
                assert tag != b'S' or not first, 'TLS fixture unsupported'
                first = False
                size = await upstream_reader.readexactly(4)
                length = struct.unpack('!I', size)[0]
                assert 4 <= length <= 16 * 1024 * 1024
                payload = await upstream_reader.readexactly(length - 4)
                if tag == b'C' and payload == b'COMMIT\0' and state['publication'] and not self.dropped.is_set():
                    self.count += 1
                    self.dropped.set()
                    # The server already committed. Do not forward CommandComplete or ReadyForQuery.
                    return
                client_writer.write(tag + size + payload)
                await client_writer.drain()
        tasks = [asyncio.create_task(incoming()), asyncio.create_task(outgoing())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            client_writer.close(); upstream_writer.close()

    def close(self):
        self.loop.call_soon_threadsafe(self.stop_event.set)
        self.thread.join(5)


def main():
    x = json.loads((Path(os.environ['C10_CONFIG_PATH'])).read_text())
    env = dict(os.environ, PYTHONPATH=os.environ.get('PYTHONPATH', '') + os.pathsep + str(ROOT),
               PYTHONDONTWRITEBYTECODE='1', CHECKPOINT_BACKEND='postgres', APP_ENV='dev',
               TELEMETRY_MODE='disabled', OTEL_ENABLED='false')
    for k in ['host', 'port', 'user', 'password']:
        env['POSTGRES_' + k.upper()] = str(x['pg_' + k])
    env['POSTGRES_DB'] = x['c10_database']
    for k in ['host', 'port', 'password']:
        env['REDIS_' + k.upper()] = str(x['redis_' + k])
    env['REDIS_DB'] = str(x['redis_database'])
    import psycopg
    report = {'before': binding(), 'checks': [], 'scenarios': [], 'status': 'RUNNING',
              'fault_method': 'SIGSTOP scheduling hooks inside real saver at driver call; real PostgreSQL COMMIT response dropped by TCP proxy',
              'not_covered': ['API/model end-to-end', 'Redis saver', 'all network timings']}
    processes, proxies = [], []
    def check(name, test):
        report['checks'].append({'name': name, 'pass': bool(test)})
        assert test, name
    def receive(proc, seconds=25):
        assert select.select([proc.stdout], [], [], seconds)[0], 'worker timeout'
        line = proc.stdout.readline()
        assert line, 'worker exited'
        return json.loads(line)
    def send(proc, op, sid=None, **kwargs):
        proc.stdin.write(json.dumps(dict(op=op, sid=sid, **kwargs)) + '\n'); proc.stdin.flush()
    def call(proc, op, sid=None, **kwargs):
        send(proc, op, sid, **kwargs)
        value = receive(proc)
        assert value.get('ok'), value
        return value['result']
    def spawn(proxy=None):
        child_env = dict(env)
        if proxy:
            child_env['POSTGRES_PORT'] = str(proxy.listen_port)
        p = subprocess.Popen([sys.executable, '-B', str(Path(__file__)), '--worker'], env=child_env,
                             cwd=os.environ['C10_EVIDENCE_DIR'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        processes.append(p)
        assert receive(p)['backend'] == 'postgres'
        return p
    def connect():
        return psycopg.connect(host=x['pg_host'], port=x['pg_port'], user=x['pg_user'],
                               password=x['pg_password'], dbname=x['c10_database'], connect_timeout=5)
    def session():
        sid = 'c10fault-' + uuid.uuid4().hex
        with connect() as conn:
            uid = 'user-' + uuid.uuid4().hex
            conn.execute('INSERT INTO users(user_id,username,role,password_hash) VALUES(%s,%s,%s,%s)',
                         (uid, uid, 'admin', 'not-a-login-password'))
            conn.execute('INSERT INTO sessions(session_id,user_id,status) VALUES(%s,%s,%s)', (sid, uid, 'running'))
        return sid
    def durable(snapshot):
        return {k: v for k, v in snapshot.items() if k != 'redis_owner'}
    try:
        observer = spawn()
        for target in ('aput', 'aput_writes'):
            before = binding()
            old, successor = spawn(), spawn()
            sid = session()
            call(old, 'reserve', sid)
            original = call(old, 'write', sid, answer='synthetic initial orphan')
            send(old, 'pause_write', sid, target=target)
            event = receive(old)
            check(target + '_paused_inside_real_saver', event.get('paused') == target)
            time.sleep(31)
            call(successor, 'reserve', sid)
            accepted_config = call(successor, 'write', sid, answer='synthetic successor ' + target)
            check(target + '_successor_published_while_old_suspended', call(successor, 'finish', sid, tokens=13))
            accepted = durable(call(observer, 'snapshot', sid))
            os.kill(old.pid, signal.SIGCONT)
            reply = receive(old)
            check(target + '_late_real_write_completed', reply.get('ok') and reply['result']['paused'])
            check(target + '_stale_publish_rejected', call(old, 'finish', sid, tokens=999) is False)
            check(target + '_late_write_keeps_pointer_status_tokens', durable(call(observer, 'snapshot', sid)) == accepted)
            value = call(observer, 'read', config=accepted_config)
            check(target + '_successor_exact_checkpoint_readable', value['checkpoint']['channel_values']['answer'] == 'synthetic successor ' + target)
            orphan = call(observer, 'read', config=reply['result']['config'])
            check(target + '_orphan_is_real_persisted_data', orphan is not None and (target == 'aput' and orphan['checkpoint']['channel_values']['answer'] == 'late orphan' or target == 'aput_writes' and any(w[1:] == ['audit', 'late orphan'] for w in orphan['pending_writes'])))
            after = binding()
            check(target + '_source_harness_stable', before == after)
            report['scenarios'].append({'name': target, 'session': sid, 'pids': [old.pid, successor.pid], 'before': before, 'after': after, 'snapshot': accepted, 'config': accepted_config})
        before = binding()
        proxy = CommitProxy(x['pg_host'], x['pg_port']); proxies.append(proxy)
        writer = spawn(proxy)
        sid = session()
        call(writer, 'reserve', sid)
        cfg = call(writer, 'write', sid, answer='synthetic committed lost ack')
        send(writer, 'finish', sid, tokens=17)
        reply = receive(writer)
        check('commit_response_actually_dropped_once', proxy.dropped.is_set() and proxy.count == 1)
        check('lost_commit_ack_returns_failure', reply.get('ok') is False and reply.get('error') == 'RuntimeStateUnavailable')
        accepted = durable(call(observer, 'snapshot', sid))
        check('lost_ack_commit_persisted_pointer_status_tokens', accepted['status'] == 'completed' and accepted['token_count'] == 17 and accepted['owner'] is None and len(accepted['publications']) == 1 and accepted['publications'][0]['checkpoint_id'] == cfg['configurable']['checkpoint_id'])
        check('lost_ack_retry_cannot_republish', call(writer, 'finish', sid, tokens=17) is False)
        check('lost_ack_failure_callback_cannot_undo', call(writer, 'fail_callback', sid) is False)
        check('lost_ack_no_duplicate_token_or_pointer', durable(call(observer, 'snapshot', sid)) == accepted)
        check('lost_ack_exact_checkpoint_readable', call(observer, 'read', config=cfg)['checkpoint']['channel_values']['answer'] == 'synthetic committed lost ack')
        after = binding()
        check('lost_ack_source_harness_stable', before == after)
        report['scenarios'].append({'name': 'lost_commit_ack', 'session': sid, 'pid': writer.pid, 'before': before, 'after': after, 'snapshot': accepted, 'config': cfg, 'response': reply})
        report['status'] = 'PASS'
    except BaseException as exc:
        report['status'] = 'FAIL'
        report['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        for p in processes:
            if p.poll() is None:
                os.kill(p.pid, signal.SIGCONT)
                try:
                    send(p, 'quit'); p.wait(timeout=12)
                except Exception:
                    p.terminate(); p.wait(timeout=5)
        for proxy in proxies:
            proxy.close()
        report['after'] = binding()
        report['source_harness_stable'] = report['before'] == report['after']
        if not report['source_harness_stable']:
            report['status'] = 'FAIL'
        report['check_count'] = len(report['checks'])
        report['failed_count'] = sum(not c['pass'] for c in report['checks'])
        output = Path(os.environ['C10_EVIDENCE_DIR']) / ('faults-' + uuid.uuid4().hex + '.json')
        output.write_text(json.dumps(report, indent=2))
        print(json.dumps({'status': report['status'], 'check_count': report['check_count'], 'failed_count': report['failed_count'], 'receipt': str(output), 'failure': report.get('failure')}))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    if '--worker' in sys.argv:
        worker()
    else:
        raise SystemExit(main())
