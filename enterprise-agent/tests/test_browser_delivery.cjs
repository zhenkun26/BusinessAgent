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

// F2-08 exercises the real existing method; this does not render a browser.
for (const [zone, expected] of [
  ['UTC', ['2026-10-20 00:15:00', '2026-03-08 06:59:59', '2026-03-08 07:00:00',
    '2026-11-01 05:59:59', '2026-11-01 06:00:00']],
  ['America/New_York', ['2026-10-19 20:15:00', '2026-03-08 01:59:59', '2026-03-08 03:00:00',
    '2026-11-01 01:59:59', '2026-11-01 01:00:00']],
  ['Asia/Shanghai', ['2026-10-20 08:15:00', '2026-03-08 14:59:59', '2026-03-08 15:00:00',
    '2026-11-01 13:59:59', '2026-11-01 14:00:00']],
]) {
  test(`F2-08 fmtTime offsets, cross-day and DST in ${zone}`, () => {
    const prior = process.env.TZ;
    try {
      process.env.TZ = zone;
      const { app } = setup({ Date });
      ['2026-10-20T00:15:00Z', '2026-03-08T06:59:59Z', '2026-03-08T07:00:00Z',
        '2026-11-01T05:59:59Z', '2026-11-01T06:00:00Z'].forEach((value, i) => {
        assert.equal(app.fmtTime(value), expected[i]);
      });
      assert.equal(app.fmtTime('2026-10-20T08:15:00+08:00'), expected[0]);
      assert.equal(app.fmtTime('2026-10-20T00:15:00+0000'), expected[0]);
      // Existing approval compatibility only; never infer a legacy citation timezone.
      assert.equal(app.fmtTime('2026-10-20 00:15:00'), expected[0]);
      assert.equal(app.fmtTime('2026-10-20T00:15:00.125Z'), expected[0]);
      assert.equal(app.fmtTime(null), '');
      assert.equal(app.fmtTime(''), '');
      assert.equal(app.fmtTime('invalid'), 'invalid');
    } finally {
      if (prior === undefined) delete process.env.TZ;
      else process.env.TZ = prior;
    }
  });
}

// F2-07: real page methods with synthetic events/focus/HTTP, never a browser DOM.
function focusFixture() {
  const body = {}, doc = { body, activeElement: body, addEventListener() {}, getElementById: () => ({ hidden: false }) };
  const env = setup({ document: doc }), focused = [];
  for (const name of ['accountPicker','sceneTrigger','loginNameInput','loginPasswordInput',
    'chatDraft','chatProgress','cancelButton','chatHeading','approvalHeading','mineHeading',
    'promptHeading','referenceHeading','statusHeading']) {
    env.app.$refs[name] = { focus() { doc.activeElement = this; focused.push(name); } };
  }
  return { ...env, doc, focused };
}
test('F2-07 bundled Vue compiles the actual template without DOM emulation', () => {
  const box = { console };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'vendor/vue-3.5.44/vue.global.prod.js'), 'utf8'), box);
  const template = html.slice(html.indexOf('<div id="app" v-cloak>'), html.indexOf('\n<script>\nconst { createApp }'));
  const render = box.Vue.compile(template, {
    // Current markup has no character references. Fail instead of pretending to decode future ones.
    decodeEntities: raw => { assert(!/&(?:#\w+|[a-z]+);/i.test(raw)); return raw; },
    onError: error => { throw error; },
  });
  assert.equal(typeof render, 'function');
});
test('F2-07 plain Enter submits once and prevents newline', () => {
  const { app } = setup(); let sent = 0, prevented = 0;
  app.sendChat = () => sent++;
  app.onDraftKeydown({ key: 'Enter', preventDefault: () => prevented++ });
  assert.equal(sent, 1); assert.equal(prevented, 1);
});
test('F2-07 composition 229 repeats modifiers and handled keys preserve editing', () => {
  const { app } = setup(); let sent = 0, prevented = 0;
  app.sendChat = () => sent++;
  for (const changes of [{ isComposing: true }, { keyCode: 229 }, { repeat: true },
    { shiftKey: true }, { ctrlKey: true }, { altKey: true }, { metaKey: true },
    { defaultPrevented: true }, { key: 'a' }]) {
    app.onDraftKeydown({ key: 'Enter', ...changes, preventDefault: () => prevented++ });
  }
  app.composing = true;
  app.onDraftKeydown({ key: 'Enter', isComposing: false, preventDefault: () => prevented++ });
  assert.equal(sent, 0); assert.equal(prevented, 0);
  app.composing = false;
  app.onDraftKeydown({ key: 'Enter', preventDefault: () => prevented++ });
  assert.equal(sent, 1);
});
test('F2-07 disclosure dismissal restores trigger and closed disclosure is inert', () => {
  const { app, focused } = focusFixture();
  app.closePicker(); app.closeScenes(); assert.equal(focused.length, 0);
  app.pickerOpen = true; app.closePicker(); assert(!app.pickerOpen); assert.equal(focused.at(-1), 'accountPicker');
  app.sceneOpen = true; app.closeScenes(); assert(!app.sceneOpen); assert.equal(focused.at(-1), 'sceneTrigger');
});
test('F2-07 account/manual/scene/reference actions focus the edited field', () => {
  const { app, focused } = focusFixture();
  app.showManualLogin(); assert(app.showManual); assert.equal(focused.at(-1), 'loginNameInput');
  app.pickUser(app.userOptions[0]); assert(!app.showManual); assert.equal(focused.at(-1), 'loginPasswordInput');
  app.sceneOpen = true; app.useScene({ text: 'synthetic scene' });
  assert.equal(app.draft, 'synthetic scene'); assert(!app.sceneOpen); assert.equal(focused.at(-1), 'chatDraft');
  app.tab = 'reference'; app.ask('synthetic record'); assert.equal(app.tab, 'chat'); assert.equal(focused.at(-1), 'chatDraft');
});
test('F2-07 navigation focus follows permitted page and approver role', () => {
  const { app, context, focused } = focusFixture(); authenticate(app);
  context.fetch = async () => reply({ items: [] });
  app.openTab('approval'); assert.equal(focused.at(-1), 'mineHeading');
  const prior = focused.length; app.openTab('prompt'); assert.equal(focused.length, prior);
  authenticate(app, 'manager'); app.openTab('approval'); assert.equal(focused.at(-1), 'approvalHeading');
  for (const tab of ['chat','reference','status']) { app.openTab(tab); assert.equal(focused.at(-1), tab + 'Heading'); }
});
test('F2-07 queued focus rejects old identity session view or newly focused control', () => {
  for (const change of ['identity','session','view','focus']) {
    const { app, doc, focused } = focusFixture(); let flush;
    app.$nextTick = fn => { flush = fn; }; app.focusRef('chatDraft');
    if (change === 'identity') app.authEpoch++;
    if (change === 'session') app.sessionEpoch++;
    if (change === 'view') app.tab = 'status';
    if (change === 'focus') doc.activeElement = {};
    flush(); assert.equal(focused.length, 0, change);
  }
});
test('F2-07 disabled or missing focus targets are harmless', () => {
  const { app, focused } = focusFixture(); app.$refs.chatDraft.disabled = true;
  app.focusRef('chatDraft'); app.focusRef('absent'); assert.equal(focused.length, 0);
});
test('F2-07 login logout and session reset restore intentional focus', async () => {
  const { app, context, focused } = focusFixture();
  context.fetch = async url => reply(url.endsWith('/me') ? identity() : { access_token: 'SYNTHETIC' });
  await app.doLogin(); assert.equal(focused.at(-1), 'chatDraft');
  app.newSession(); assert.equal(focused.at(-1), 'chatDraft');
  app.doLogout(); assert.equal(focused.at(-1), 'loginPasswordInput');
  app.showManual = true; app.doLogout(); assert.equal(focused.at(-1), 'loginNameInput');
});
test('F2-07 late login cannot focus or announce into a different identity', async () => {
  const { app, context, focused } = focusFixture(), wait = deferred(); context.fetch = () => wait.promise;
  const pending = app.doLogin(); app.doLogout(); const count = focused.length;
  wait.resolve(reply({ access_token: 'OLD' })); await pending;
  assert.equal(focused.length, count); assert.equal(app.chatStatus, '');
});
test('F2-07 tokens and timer do not announce; final waits for stream validation', async () => {
  const { app, context, doc, focused } = focusFixture(), wait = deferred(); authenticate(app); app.draft = 'synthetic';
  const response = stream([event({ type: 'token', data: 'SYNTHETIC_PRIVATE_ANSWER' }), event(final())], () => wait.promise);
  context.fetch = async () => response;
  const pending = app.sendChat(); await new Promise(setImmediate);
  assert.equal(app.chatStatus, '请求已发送，正在处理。'); assert.equal(doc.activeElement, app.$refs.chatProgress);
  app.elapsed = 99; assert(!app.chatStatus.includes('99')); assert(!app.chatStatus.includes('SYNTHETIC_PRIVATE_ANSWER'));
  wait.resolve({ done: true }); await pending;
  assert.equal(app.chatStatus, '回答已完成，可在对话记录中阅读。'); assert.equal(focused.at(-1), 'chatDraft');
});
test('F2-07 stream completion preserves focus in other control or page', async () => {
  for (const target of ['other-control','other-page']) {
    const { app, context, doc } = focusFixture(), wait = deferred(); authenticate(app); app.draft = 'synthetic';
    context.fetch = async () => stream([event(final())], () => wait.promise);
    const pending = app.sendChat(); await new Promise(setImmediate);
    const destination = target === 'other-page' ? app.$refs.statusHeading : {};
    if (target === 'other-page') app.tab = 'status'; doc.activeElement = destination;
    wait.resolve({ done: true }); await pending; assert.equal(doc.activeElement, destination);
  }
});
test('F2-07 late stream cannot announce into a new session or login', async () => {
  for (const reset of ['logout','session']) {
    const { app, context } = focusFixture(), wait = deferred(); authenticate(app); app.draft = 'synthetic';
    context.fetch = () => wait.promise; const pending = app.sendChat();
    if (reset === 'logout') app.doLogout(); else { app.sessionEpoch++; app.chatStatus = ''; }
    wait.resolve(stream([event(final())])); await pending; assert.equal(app.chatStatus, '');
  }
});
test('F2-07 cancellation receipt stays requested until server termination', async () => {
  const { app, context } = focusFixture(); authenticate(app); app.pending = true; app.sessionId = 'synthetic';
  app.chatStatus = '请求已发送，正在处理。'; context.fetch = async () => reply({ cancelled: true });
  await app.cancelChat(); assert(app.cancelRequested); assert(app.toast.includes('等待服务端终态'));
  assert(!app.chatStatus.includes('确认取消')); assert(!app.chatStatus.includes('已完成'));
});
for (const [label, events, expected] of [
  ['cancelled', [event({ type: 'cancelled' })], '服务端已确认取消本次对话。'],
  ['server error', [event({ type: 'error' })], '未确认完成'],
  ['premature EOF', [event({ type: 'token', data: 'partial' })], '未确认完成'],
  ['duplicate terminal', [event(final()), event(final())], '未确认完成'],
  ['malformed after final', [event(final()), 'data: {\n\n'], '未确认完成'],
]) {
  test('F2-07 truthful lifecycle announcement: ' + label, async () => {
    const { app, context } = focusFixture(); authenticate(app); app.draft = 'synthetic';
    context.fetch = async () => stream([...events]); await app.sendChat(); assert(app.chatStatus.includes(expected));
    assert(!app.chatStatus.includes('partial'));
  });
}
test('F2-07 approval removal restores heading without stealing another control', async () => {
  for (const moved of [false, true]) {
    const { app, context, doc } = focusFixture(); authenticate(app, 'manager'); app.tab = 'approval';
    const trigger = {}, other = {}; doc.activeElement = trigger;
    context.fetch = async (url, opts) => {
      if (url.endsWith('/me')) return reply(identity('manager'));
      if (opts.method === 'POST') { if (moved) doc.activeElement = other; return reply({ approval_id: 'synthetic', status: 'approved_pending_reauth' }); }
      return reply({ items: [] });
    };
    await app.decide({ approval_id: 'synthetic' }, 'approved', trigger);
    assert.equal(doc.activeElement, moved ? other : app.$refs.approvalHeading);
  }
});
test('F2-07 empty unavailable and loading text stay distinct and notify errors', async () => {
  const { app, context } = setup(); authenticate(app);
  context.fetch = async () => reply({ items: [] }); const pending = app.loadMine();
  assert.equal(app.viewStatus('myApprovals'), '正在加载…'); await pending;
  assert.equal(app.loadState.myApprovals, 'ready'); assert.equal(app.myApprovals.length, 0);
  context.fetch = async () => reply({}, 503); await app.loadMine();
  assert.equal(app.viewStatus('myApprovals'), '数据不可用，请刷新重试'); assert(app.toast.includes('503'));
});

test('Integrated human-review holds block decision and requester resume before network', async () => {
  const { app, context } = setup(); authenticate(app, 'manager');
  let calls = 0, prompts = 0;
  context.fetch = async () => { calls++; throw new Error('held request must not dispatch'); };
  context.window.prompt = () => { prompts++; return ''; };
  const held = { approval_id: 'held', status: 'approved_pending_reauth',
    human_review_required: true, review_message: 'Review retained evidence' };
  await app.resume(held);
  await app.decide(held, 'approved');
  await app.decide(held, 'rejected');
  assert.equal(calls, 0); assert.equal(prompts, 0);
  assert.equal(held.status, 'approved_pending_reauth');
});
test('Integrated hold notices coexist with accessible confirmation controls', () => {
  assert(html.includes('v-if="a.human_review_required"'));
  assert(html.includes('v-if="!m.human_review_required && m.status==='));
  assert(html.includes('确认执行审批 '));
  assert(html.includes('请确认操作内容后以当前身份执行'));
});

function evidence(id, updates = {}) {
  return { approval_id: id, status: 'execution_unknown', human_review_required: true,
    automatic_release: false, automatic_retry: false,
    operations: [{ operation_id: 'op-' + id, state: 'unknown', receipt_present: true,
      receipt_verified: true, observed_at: '2026-11-07T12:00:00Z', private_payload: 'never-render' }],
    ...updates };
}
test('Evidence is a read-only snapshot and never clears holds or mutation uncertainty', async () => {
  const { app, context } = setup(); authenticate(app);
  app.uncertain['resume:a'] = true;
  const paths = [];
  context.fetch = async (url, opts) => { paths.push([url, opts.method]); return reply(evidence('a')); };
  await app.loadApprovalEvidence('a');
  assert.equal(app.approvalEvidenceStatus, 'execution_unknown');
  assert.equal(app.approvalEvidence.length, 1);
  assert(!('private_payload' in app.approvalEvidence[0]));
  assert.equal(app.uncertain['resume:a'], true);
  assert(paths.every(([url, method]) => url.endsWith('/a/evidence') && !method));
});
test('Evidence latest selection wins; close and logout reject late results', async () => {
  const { app, context } = setup(); authenticate(app);
  let first = deferred();
  context.fetch = async url => url.endsWith('/a/evidence') ? first.promise : reply(evidence('b'));
  const old = app.loadApprovalEvidence('a'); await app.loadApprovalEvidence('b');
  first.resolve(reply(evidence('a'))); await old;
  assert.equal(app.approvalEvidenceId, 'b'); assert.equal(app.approvalEvidence[0].operation_id, 'op-b');
  for (const action of ['closeApprovalEvidence', 'doLogout']) {
    first = deferred(); authenticate(app);
    const pending = app.loadApprovalEvidence('a'); app[action]();
    first.resolve(reply(evidence('a'))); await pending;
    assert.equal(app.approvalEvidence.length, 0); assert.equal(app.approvalEvidenceId, '');
  }
});
test('Denied or malformed evidence discards prior snapshot without releasing hold', async () => {
  const { app, context } = setup(); authenticate(app);
  context.fetch = async () => reply(evidence('a')); await app.loadApprovalEvidence('a');
  context.fetch = async () => reply({}, 403); await app.loadApprovalEvidence('a');
  assert.equal(app.approvalEvidence.length, 0);
  context.fetch = async () => reply(evidence('a', { automatic_release: true }));
  await app.loadApprovalEvidence('a');
  assert.equal(app.loadState.approvalEvidence, 'unavailable'); assert.equal(app.approvalEvidence.length, 0);
});

test('Evidence close restores approval heading without stealing a newer focus', () => {
  for (const moved of [false, true]) {
    const { app, doc } = focusFixture(); authenticate(app, 'manager'); app.tab = 'approval';
    const close = {}, other = {}; doc.activeElement = moved ? other : close;
    app.approvalEvidenceId = 'a'; app.closeApprovalEvidence(close);
    assert.equal(doc.activeElement, moved ? other : app.$refs.approvalHeading);
    assert.equal(app.approvalEvidenceId, '');
  }
});


function demoDocument(profile = 'synthetic-demo-v1') {
  return { body: { getAttribute: name => name === 'data-businessagent-profile' ? profile : null },
    addEventListener() {}, getElementById: () => ({ hidden: false }) };
}
function demoRejection(status = 403, profile = 'synthetic-demo-v1', detail = 'DEMO_UNSUPPORTED_OPERATION') {
  return { ...reply({ detail }, status), headers: { get: name => name === 'x-businessagent-profile' ? profile : 'application/json' } };
}
test('Explicit server demo marker restricts greeting suggestions and business navigation', () => {
  const { app } = setup({ document: demoDocument() }); authenticate(app, 'admin');
  assert.equal(app.syntheticDemo, true);
  assert.match(app.roleIntro, /固定文本/);
  assert.match(app.roleIntro, /未启用模型、RAG、业务工具、审批/);
  assert.deepEqual(Array.from(app.welcomeSuggestions, s => s.text), ['你好', '您好']);
  assert.deepEqual(Array.from(app.sceneGroups, g => g.cat), ['合成问候']);
  for (const tab of ['approval', 'prompt', 'reference', 'status']) { app.openTab(tab); assert.equal(app.tab, 'chat'); }
  app.startSso(); assert.match(app.loginErr, /不支持 SSO/);
  for (const tab of ['approval', 'reference', 'status'])
    assert(html.includes('v-if="!syntheticDemo" :class="{active: tab===\'' + tab + '\'}"'));
  assert(html.includes('v-if="!syntheticDemo && isApprover"'));
  assert(html.includes('v-if="!syntheticDemo && !m.rejected && !m.cancelled && !m.incomplete && !pending"'));
});
test('URL and storage cannot activate demo profile or replace production welcome', () => {
  const { app } = setup({ location: { protocol: 'https:', search: '?profile=synthetic-demo-v1' },
    localStorage: storage({ profile: 'synthetic-demo-v1' }), sessionStorage: storage({ profile: 'synthetic-demo-v1' }) });
  authenticate(app, 'admin'); assert.equal(app.syntheticDemo, false);
  assert.match(app.roleIntro, /各业务工具也能直接操作/);
  assert(app.welcomeSuggestions.some(s => s.text.includes('订单')));
  assert.equal(setup({ document: demoDocument('other') }).app.syntheticDemo, false);
});
test('Confirmed demo predispatch rejection says unsupported and not executed', async () => {
  const { app } = setup({ document: demoDocument(), fetch: async () => demoRejection() });
  authenticate(app); app.draft = '帮我发邮件'; await app.sendChat();
  const answer = app.messages[1];
  assert.equal(answer.rejected, true); assert.equal(answer.incomplete, false);
  assert.match(answer.text, /执行前拒绝，未执行业务操作/);
  assert.doesNotMatch(answer.text, /未确认完成|勿直接重复/);
  assert.match(app.chatStatus, /未执行业务操作/); assert.equal(app.pending, false);
});
test('Generic or mismatched demo errors and production rejection retain uncertain outcome', async () => {
  for (const [demo, status, profile, detail] of [
    [true, 403, '', 'DEMO_UNSUPPORTED_OPERATION'],
    [true, 403, 'synthetic-demo-v1', 'FORBIDDEN'],
    [true, 500, 'synthetic-demo-v1', 'DEMO_UNSUPPORTED_OPERATION'],
    [false, 403, 'synthetic-demo-v1', 'DEMO_UNSUPPORTED_OPERATION'],
  ]) {
    const { app } = setup({ document: demoDocument(demo ? 'synthetic-demo-v1' : ''),
      fetch: async () => demoRejection(status, profile, detail) });
    authenticate(app); app.draft = '帮我发邮件'; await app.sendChat();
    assert.equal(app.messages[1].incomplete, true);
    assert.notEqual(app.messages[1].rejected, true);
    assert.match(app.chatStatus, /未确认完成/);
    assert.doesNotMatch(app.messages[1].text, /未执行业务操作/);
  }
});
test('Malformed and stale demo rejection cannot falsely confirm an outcome', async () => {
  const pending = deferred();
  const { app, context } = setup({ document: demoDocument() });
  authenticate(app); app.draft = '帮我发邮件';
  context.fetch = async () => ({ ...demoRejection(), text: () => pending.promise });
  const sending = app.sendChat(); await Promise.resolve(); await Promise.resolve();
  app.doLogout(); pending.resolve(JSON.stringify({ detail: 'DEMO_UNSUPPORTED_OPERATION' }));
  await sending; assert.equal(app.messages.length, 0);
  authenticate(app); app.draft = '帮我发邮件';
  context.fetch = async () => ({ ...demoRejection(), text: async () => 'invalid json' });
  await app.sendChat(); assert.equal(app.messages[1].incomplete, true);
  assert.match(app.chatStatus, /未确认完成/);
});

(async () => {
  for (const [name, fn] of tests) { await fn(); console.log('PASS ' + name); }
  console.log(`PASS: ${tests.length} C20/F2-08/F2-07 cases; VM/static/compile only, real browser/API acceptance BLOCKED`);
})().catch(error => { console.error(error); process.exitCode = 1; });
