// C20 reviewed entry: read-only source/assets, Node VM and injected browser/HTTP only.
// Never starts a server/browser, installs packages, writes files or calls a real API.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const root = path.join(__dirname, '../app/static');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = html.slice(html.indexOf('<script>\nconst { createApp }') + 8, html.lastIndexOf('</script>'));
const tests = [];
function test(name, fn) { tests.push([name, fn]); }
function storage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return { getItem: key => data.get(key), removeItem: key => data.delete(key),
    setItem: (key, value) => data.set(key, value), data };
}
function reply(data, status = 200) {
  return { status, ok: status >= 200 && status < 300, text: async () => JSON.stringify(data) };
}
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }
function setup(extra = {}) {
  let app, options, timerId = 0;
  const timers = new Map();
  const context = { AbortController, TextDecoder, TextEncoder, console,
    location: { protocol: 'https:' }, window: { prompt: () => '' },
    document: { addEventListener() {}, getElementById: () => ({ hidden: false }) },
    localStorage: storage(), sessionStorage: storage(),
    setTimeout: (fn, ms) => { timers.set(++timerId, { fn, ms }); return timerId; },
    clearTimeout: id => timers.delete(id), setInterval: () => 0, clearInterval() {},
    fetch: async () => { throw new Error('UNEXPECTED_NETWORK_DOUBLE'); },
    Vue: { createApp: opts => { options = opts; return { mount: () => {
      app = Object.fromEntries(Object.entries(opts.data()).filter(([k]) => !/^[_$]/.test(k)));
      app.$nextTick = fn => fn(); app.$refs = { chatBody: {} };
      for (const [k, fn] of Object.entries(opts.methods)) app[k] = fn.bind(app);
      for (const [k, fn] of Object.entries(opts.computed)) Object.defineProperty(app, k, { get: fn.bind(app) });
    } }; } }, ...extra };
  vm.runInNewContext(script, context);
  return { app, context, timers, mounted: () => options.mounted.call(app) };
}
function identity(role = 'salesperson') { return { user_id: 'fixture', username: 'Fixture', role, department: 'dept_sales' }; }
function authenticate(app, role = 'salesperson') {
  Object.assign(app, { token: 'SYNTHETIC', authReady: true, userId: 'fixture', username: 'Fixture', role, userDept: 'dept_sales' });
}
function stream(chunks, tail) {
  const reader = { cancelled: false, read: async () => chunks.length
    ? { done: false, value: new TextEncoder().encode(chunks.shift()) } : tail ? tail() : { done: true },
    cancel: async () => { reader.cancelled = true; } };
  return { status: 200, ok: true, headers: { get: () => 'text/event-stream; charset=utf-8' }, body: { getReader: () => reader }, reader };
}
const event = data => 'data: ' + JSON.stringify(data) + '\n\n';
const final = (sid = 'session') => ({ type: 'final', data: { session_id: sid, answer: 'Confirmed', sources: [], confidence: 0.8, intent: 'general' } });

test('local assets match registry-derived manifest, SRI and retained licenses', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'vendor/manifest.json')));
  assert.equal(manifest.packages.length, 3);
  assert(!/<script[^>]+src="https?:/.test(html));
  for (const pkg of manifest.packages) {
    assert(pkg.files.some(f => f.file.includes('LICENSE')));
    for (const f of pkg.files) {
      const bytes = fs.readFileSync(path.join(root, 'vendor', f.file));
      assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), f.sha256);
      assert.equal('sha384-' + crypto.createHash('sha384').update(bytes).digest('base64'), f.sri);
      if (f.file.endsWith('.js')) { new vm.Script(bytes.toString()); assert(html.includes(f.file)); assert(html.includes(f.sri)); }
    }
  }
});
test('bundled Marked exposes a synchronous browser parser', () => {
  const box = {}; vm.runInNewContext(fs.readFileSync(path.join(root, 'vendor/marked-18.1.1/marked.umd.js'), 'utf8'), box);
  assert.equal(typeof box.marked.parse, 'function'); assert(box.marked.parse('**text**').includes('<strong>text</strong>'));
});
test('missing Vue leaves static failure without mounting', () => {
  assert.doesNotThrow(() => setup({ Vue: undefined })); assert(html.includes('id="boot-error"')); assert(html.includes('v-cloak'));
});
test('SSO handoff cannot provide trusted role before /me', async () => {
  const { app, context } = setup({ sessionStorage: storage({ ea_sso_once: JSON.stringify({ access_token: 'TOKEN', role: 'admin' }) }) });
  assert.equal(app.role, ''); assert.equal(app.authReady, false); assert.equal(context.sessionStorage.data.size, 0);
  context.fetch = async () => reply(identity()); await app.refreshIdentity(); assert.equal(app.role, 'salesperson'); assert(!app.isApprover);
});
for (const role of ['salesperson', 'customer_service', 'finance', 'manager', 'admin']) {
  test('role gates: ' + role, () => {
    const { app } = setup(); authenticate(app, role);
    assert.equal(app.isApprover, ['manager','admin'].includes(role)); assert.equal(app.isAdmin, role === 'admin');
    app.openTab('prompt'); assert.equal(app.tab, app.isApprover ? 'prompt' : 'chat');
  });
}
test('local login ignores role claims and verifies current identity', async () => {
  const { app, context } = setup(); const calls = [];
  context.fetch = async (url, opts) => { calls.push(url); return reply(url.endsWith('/me') ? identity() : { access_token: 'NEW', role: 'admin' }); };
  app.loginPassword = 'fixture-password'; await app.doLogin(); assert(app.authReady); assert.equal(app.role, 'salesperson');
  assert.equal(app.loginPassword, ''); assert.deepEqual(calls, ['/api/v1/auth/login','/api/v1/auth/me']);
});
test('duplicate login has one request and late result cannot restore logout', async () => {
  const { app, context } = setup(), wait = deferred(); let calls = 0;
  context.fetch = () => { calls++; return wait.promise; };
  const pending = app.doLogin(); await app.doLogin(); assert.equal(calls, 1); app.doLogout();
  wait.resolve(reply({ access_token: 'OLD' })); await pending; assert.equal(app.token, '');
});
test('identity change clears private views and disables management', async () => {
  const { app, context } = setup(); authenticate(app, 'admin'); app.documents = ['private']; app.prompts = { private: [] };
  context.fetch = async () => reply(identity()); await assert.rejects(app.refreshIdentity()); assert.equal(app.token, ''); assert(!app.isAdmin); assert.equal(app.documents.length, 0);
});
test('invalid identity never opens UI', async () => {
  const { app, context } = setup(); app.token = 'TEMP'; context.fetch = async () => reply({ ...identity(), role: 'root' });
  await assert.rejects(app.refreshIdentity()); assert(!app.authReady); assert.equal(app.token, '');
});
test('late SSO failure cannot log out a different identity', async () => {
  const { app, context, mounted } = setup(), wait = deferred(); app.token = 'OLD'; context.fetch = () => wait.promise;
  mounted(); app.doLogout(); authenticate(app); wait.resolve(reply({}, 401)); await new Promise(setImmediate); assert.equal(app.token, 'SYNTHETIC');
});
test('protected method denies ordinary role before write', async () => {
  const { app, context } = setup(); authenticate(app); let writes = 0;
  context.fetch = async (url, opts) => { if (opts.method) writes++; return reply(identity()); };
  app.promptDrafts.p = 'content'; await app.createVersion('p'); await app.loadDocuments(); assert.equal(writes, 0); assert.equal(app.documents.length, 0);
});
test('cancelled approval prompt performs no request', async () => {
  const { app, context } = setup(); authenticate(app, 'manager'); context.window.prompt = () => null;
  let calls = 0; context.fetch = async () => { calls++; return reply({}); }; await app.decide({ approval_id: 'a' }, 'approved'); assert.equal(calls, 0);
});
test('ordinary role approval page loads own records without a false permission error', async () => {
  const { app, context } = setup(); authenticate(app); const calls = [];
  context.fetch = async url => { calls.push(url); return reply({ items: [] }); };
  app.openTab('approval'); await new Promise(setImmediate);
  assert.deepEqual(calls, ['/api/v1/approvals/mine']); assert.equal(app.toast, '');
  assert.equal(app.loadState.myApprovals, 'ready');
});
test('approval duplicate guard and confirmed state are independent of message text', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app, 'manager'); let writes = 0;
  context.fetch = async (url, opts) => { if (url.endsWith('/me')) return reply(identity('manager'));
    if (opts.method === 'POST') { writes++; return wait.promise; } return reply({ items: [] }); };
  const row = { approval_id: 'a' }, pending = app.decide(row, 'approved'); await app.decide(row, 'rejected');
  await new Promise(setImmediate); assert.equal(writes, 1);
  wait.resolve(reply({ approval_id: 'a', status: 'execution_unknown', message: 'SUCCESS' })); await pending;
  assert.equal(row.resultStatus, 'execution_unknown'); assert(!row.result.includes('成功'));
});
test('lost mutation response remains uncertain and blocks immediate replay', async () => {
  const { app, context } = setup(); authenticate(app, 'manager'); let writes = 0;
  context.fetch = async (url) => { if (url.endsWith('/me')) return reply(identity('manager')); writes++; throw new Error('lost'); };
  const row = { approval_id: 'a' }; await app.decide(row, 'approved'); await app.decide(row, 'approved');
  assert.equal(writes, 1); assert(app.uncertain['approval:a']); assert.equal(row.result, undefined);
});
test('malformed success does not certify an approval outcome', async () => {
  const { app, context } = setup(); authenticate(app, 'manager'); context.fetch = async url => reply(url.endsWith('/me') ? identity('manager') : {});
  const row = { approval_id: 'a' }; await app.decide(row, 'approved'); assert(app.uncertain['approval:a']); assert.equal(row.result, undefined);
});
test('resume requires a pending confirmation state', async () => {
  const { app, context } = setup(); authenticate(app); let calls = 0; context.fetch = async () => { calls++; return reply({}); };
  await app.resume({ approval_id: 'a', status: 'executed' }); assert.equal(calls, 0);
});
test('ledger outage clears rows without synthetic fallback', async () => {
  const { app, context } = setup(); authenticate(app, 'admin'); app.documents = ['stale'];
  context.fetch = async url => reply(url.endsWith('/me') ? identity('admin') : {}, url.endsWith('/me') ? 200 : 503);
  await app.loadDocuments(); assert.equal(app.documents.length, 0); assert.equal(app.loadState.documents, 'unavailable');
});
test('latest list request wins and malformed lists stay unavailable', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app); let count = 0;
  context.fetch = () => ++count === 1 ? wait.promise : Promise.resolve(reply({ items: [{ approval_id: 'new' }] }));
  const old = app.loadMine(); await app.loadMine(); wait.resolve(reply({ items: [{ approval_id: 'old' }] })); await old;
  assert.equal(app.myApprovals[0].approval_id, 'new'); context.fetch = async () => reply({ items: [null] }); await app.loadMine(); assert.equal(app.loadState.myApprovals, 'unavailable');
});
test('empty and denied lists remain distinguishable', async () => {
  const { app, context } = setup(); authenticate(app); context.fetch = async () => reply({ items: [] });
  await app.loadMine(); assert.equal(app.loadState.myApprovals, 'ready'); context.fetch = async () => reply({}, 403);
  await app.loadMine(); assert.equal(app.loadState.myApprovals, 'unavailable');
});
test('API timeout aborts once without retry', async () => {
  const { app, context, timers } = setup(); let calls = 0;
  context.fetch = (url, opts) => { calls++; return new Promise((resolve, reject) => opts.signal.addEventListener('abort', () => reject({ name: 'AbortError' }))); };
  const pending = app.api('/fixture', { method: 'POST' }); [...timers.values()].find(t => t.ms === 15000).fn();
  await assert.rejects(pending, e => e.outcomeUnknown); assert.equal(calls, 1);
});
test('old 401 never clears a new login', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app); context.fetch = () => wait.promise;
  const pending = app.api('/fixture'); app.doLogout(); app.token = 'NEW'; wait.resolve(reply({}, 401));
  await assert.rejects(pending); assert.equal(app.token, 'NEW');
});
test('history cannot cross a new conversation', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app); app.sessionId = 'old'; context.fetch = () => wait.promise;
  const pending = app.loadHistory(); app.newSession(); wait.resolve(reply({ found: true, final_answer: 'private old' })); await pending; assert.equal(app.messages.length, 0);
});
test('history is labelled as a snapshot instead of execution success', async () => {
  const { app, context } = setup(); authenticate(app); app.sessionId = 's'; context.fetch = async () => reply({ found: true, session_status: 'failed', final_answer: 'old answer' });
  await app.loadHistory(); assert(app.messages[0].incomplete); assert(app.messages[0].text.includes('failed'));
});
test('SSE handles fragmented CRLF and uses final answer as authority', async () => {
  const { app, context } = setup(); authenticate(app); app.draft = 'question';
  const bytes = (event({ type: 'token', session_id: 'session', data: 'partial' }) + event(final())).replaceAll('\n','\r\n');
  context.fetch = async () => stream([bytes.slice(0,13), bytes.slice(13,-1), bytes.slice(-1)]); await app.sendChat();
  assert.equal(app.messages[1].text, 'Confirmed'); assert.equal(app.messages[1].incomplete, false); assert.equal(app.pending, false);
});
for (const [name, payload] of [
  ['premature EOF', event({ type: 'token', data: 'partial' })],
  ['malformed JSON', 'data: {bad}\n\n'], ['missing final separator', 'data: ' + JSON.stringify(final())],
  ['wrong session', event(final('other'))], ['duplicate terminal', event(final()) + event(final())],
  ['unknown event', event({ type: 'unknown' })], ['oversized frame', 'x'.repeat(262145)],
]) test('SSE fails closed: ' + name, async () => {
  const { app, context } = setup(); authenticate(app); app.draft = 'question'; if (name === 'wrong session') app.sessionId = 'session';
  context.fetch = async () => stream([payload]); await app.sendChat(); assert(app.messages[1].incomplete); assert.equal(app.messages[1].cancelled, false);
});
test('cancellation acceptance does not abort stream or claim stopped', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app); app.draft = 'question';
  let reads = 0, aborted = false;
  context.fetch = async (url, opts) => {
    if (url.endsWith('/cancel')) return reply({ cancelled: true });
    opts.signal.addEventListener('abort', () => { aborted = true; });
    return stream([event({ type: 'progress', session_id: 'session', node: 'planner' })], () => ++reads === 1 ? wait.promise : { done: true });
  };
  const pending = app.sendChat(); await new Promise(setImmediate); await app.cancelChat();
  assert(app.pending); assert(app.cancelRequested); assert(!aborted); assert.equal(app.messages.length, 1);
  wait.resolve({ done: false, value: new TextEncoder().encode(event({ type: 'cancelled' })) }); await pending;
  assert.equal(app.messages[1].cancelled, true); assert.equal(app.messages[1].incomplete, false);
});
test('logout discards stream results and preserves a new request state', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app); app.draft = 'question'; context.fetch = () => wait.promise;
  const pending = app.sendChat(); app.doLogout(); authenticate(app); app.pending = true;
  wait.resolve(stream([event(final())])); await pending; assert.equal(app.messages.length, 0); assert.equal(app.pending, true);
});
test('new conversation and duplicate send cannot replace an active stream', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app); app.draft = 'question'; let calls = 0;
  context.fetch = () => { calls++; return wait.promise; }; const pending = app.sendChat(); const generation = app.sessionEpoch;
  app.newSession(); app.draft = 'duplicate'; await app.sendChat(); assert.equal(calls, 1); assert.equal(app.sessionEpoch, generation);
  wait.resolve(stream([event(final())])); await pending;
});
test('prompt validation rejects invalid version and weight before mutation', async () => {
  const { app } = setup(); authenticate(app, 'manager'); app.activateVer.p = -1; await app.activate('p');
  app.weights.p_1 = Infinity; await app.setTraffic('p', [{ status: 'active', version: 1 }]); assert.equal(Object.keys(app.busy).length, 0);
});
test('current login 401 leaves an actionable login error', async () => {
  const { app, context } = setup(); context.fetch = async () => reply({}, 401);
  await app.doLogin(); assert.equal(app.token, ''); assert(app.loginErr.includes('登录')); assert(!app.logging);
});
test('manager can create, activate and adjust traffic with confirmed contracts', async () => {
  const { app, context } = setup(); authenticate(app, 'manager'); const writes = [];
  context.fetch = async (url, opts) => {
    if (url.endsWith('/me')) return reply(identity('manager'));
    if (!opts.method) return reply({ prompts: { p: [{ version: 2, status: 'active' }] } });
    writes.push([url, JSON.parse(opts.body)]);
    if (url.endsWith('/versions')) return reply({ name: 'p', version: 2, status: 'draft' });
    if (url.endsWith('/activate')) return reply({ name: 'p', version: 2, status: 'active' });
    return reply({ name: 'p', weights: { '2': 100 } });
  };
  app.promptDrafts.p = 'New content'; await app.createVersion('p'); assert.equal(app.promptDrafts.p, '');
  app.activateVer.p = 2; await app.activate('p'); app.weights.p_2 = 100;
  await app.setTraffic('p', [{ status: 'active', version: 2 }]);
  assert.equal(writes.length, 3); assert.equal(Object.keys(app.uncertain).length, 0);
  assert.equal(app.prompts.p[0].version, 2);
});
test('confirmed resume retains executing rather than claiming success', async () => {
  const { app, context } = setup(); authenticate(app); let writes = 0;
  context.fetch = async (url, opts) => {
    if (url.endsWith('/me')) return reply(identity());
    if (opts.method) { writes++; return reply({ approval_id: 'a', status: 'executing' }); }
    return reply({ items: [{ approval_id: 'a', status: 'executing' }] });
  };
  const row = { approval_id: 'a', status: 'approved_pending_reauth' };
  await app.resume(row); await app.resume(row);
  assert.equal(writes, 1); assert.equal(row.status, 'executing'); assert(!app.toast.includes('成功'));
});
test('late successful management response cannot restore another login views', async () => {
  const { app, context } = setup(), wait = deferred(); authenticate(app, 'admin');
  context.fetch = async url => url.endsWith('/me') ? reply(identity('admin')) : wait.promise;
  const pending = app.loadDocuments(); await new Promise(setImmediate); app.doLogout(); authenticate(app);
  wait.resolve(reply({ data: { items: [{ document_id: 'private' }] } })); await pending;
  assert.equal(app.documents.length, 0); assert.equal(app.role, 'salesperson');
});
test('static role gates and synthetic data boundaries are visible', () => {
  assert(html.includes('v-if="isAdmin"')); assert(html.includes('v-if="isApprover" v-show="tab===\'prompt\'"'));
  assert(html.includes('静态示例，未连接当前业务系统')); assert(!html.includes('与 CRM/工单系统 API 同源'));
  assert(html.includes('recipient@example.invalid')); assert(!html.includes('documents: [\n        {'));
});

(async () => {
  for (const [name, fn] of tests) { await fn(); console.log('PASS ' + name); }
  console.log(`PASS: ${tests.length} C20 cases; VM/static only, real browser/API acceptance BLOCKED`);
})().catch(error => { console.error(error); process.exitCode = 1; });
