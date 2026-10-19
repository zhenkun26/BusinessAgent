// Executes the actual inline UI script in a VM with fake browser globals.
// No browser/DOM, network, package installation, file writes or cleanup.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../app/static/index.html'), 'utf8');
const script = html.slice(html.indexOf('<script>\nconst { createApp }') + 8, html.lastIndexOf('</script>'));
const marker = 'SYNTHETIC_BROWSER_CREDENTIAL';

function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return { values, getItem: k => values.get(k) || null,
    setItem: (k, v) => values.set(k, v), removeItem: k => values.delete(k) };
}

function setup(extra = {}) {
  let app;
  const context = {
    localStorage: storage({ ea_token: marker, ea_sid: 'old-session' }), sessionStorage: storage(),
    Vue: { createApp: options => ({ mount: () => {
      // Vue does not proxy data keys beginning with _ or $ onto the instance.
      app = Object.fromEntries(Object.entries(options.data()).filter(([key]) => !/^[_$]/.test(key)));
      for (const [key, fn] of Object.entries(options.methods)) app[key] = fn.bind(app);
    } }) },
    location: { protocol: 'https:' }, window: {}, document: {},
    setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {},
    AbortController,
    fetch: async () => { throw new Error('Unexpected network attempt'); }, ...extra,
  };
  vm.runInNewContext(script, context);
  return { app, context };
}

(async () => {
  let passed = 0;
  const payload = '<img src=x onerror="attack()"><script>attack()</script>&\'';
  for (const globals of [
    {}, { marked: { parse: () => payload } },
    { marked: { parse: () => { throw new Error('renderer'); } }, DOMPurify: { sanitize: x => x } },
    { marked: { parse: () => payload }, DOMPurify: { sanitize: () => { throw new Error('sanitizer'); } } },
    { marked: { parse: () => payload }, DOMPurify: { isSupported: false, sanitize: x => x } },
    { marked: { parse: () => ({}) }, DOMPurify: { sanitize: x => x } },
    { marked: { parse: () => payload }, DOMPurify: { sanitize: () => ({}) } },
  ]) {
    const { app } = setup(globals);
    const output = app.renderMd(payload);
    assert(!output.includes('<') && !output.includes('>'));
    assert(output.includes('&lt;img') && output.includes('&amp;') && output.includes('&#39;'));
    passed++;
  }
  {
    let sanitized = 0;
    const { app } = setup({ marked: { parse: () => payload },
      DOMPurify: { sanitize: input => { assert.equal(input, payload); sanitized++; return '<p>safe</p>'; } } });
    assert.equal(app.renderMd(payload), '<p>safe</p>');
    assert.equal(sanitized, 1); passed++;
  }
  {
    const { app, context } = setup();
    assert.equal(app.token, ''); assert.equal(context.localStorage.values.size, 0); passed++;
  }
  {
    const handoff = storage({ ea_sso_once: JSON.stringify({ access_token: marker, username: 'synthetic' }) });
    const first = setup({ sessionStorage: handoff });
    assert.equal(first.app.token, marker); assert.equal(handoff.values.size, 0);
    assert.equal(setup({ sessionStorage: handoff }).app.token, ''); passed++;
  }
  {
    const { app, context } = setup();
    let body;
    context.fetch = async (url, opts) => {
      if (url.endsWith('/me')) return { ok: true, status: 200, text: async () => JSON.stringify({
        user_id: 'synthetic-id', username: 'synthetic', role: 'salesperson', department: '' }) };
      if (opts.body) body = JSON.parse(opts.body);
      return { ok: true, status: 200, text: async () => JSON.stringify({ access_token: marker, role: 'salesperson' }) };
    };
    app.loginPassword = 'synthetic-password';
    await app.doLogin();
    assert.equal(body.password, 'synthetic-password'); assert.equal(app.loginPassword, '');
    assert.equal(app.token, marker);
    assert(Number.isFinite(app.authEpoch));
    await app.api('/synthetic-after-login', { body: '{}' });
    assert.equal(context.localStorage.values.size + context.sessionStorage.values.size, 0); passed++;
  }
  {
    const { app, context } = setup();
    let aborted = 0;
    app.token = marker; app.sessionId = 's'; app.loginPassword = marker;
    app.streamAbort = { abort: () => aborted++ }; app.messages = ['private']; app.myApprovals = ['private'];
    context.fetch = async () => ({ status: 401 });
    await assert.rejects(app.api('/synthetic'));
    assert.equal(app.token, ''); assert.equal(app.loginPassword, ''); assert.equal(app.sessionId, '');
    assert.equal(app.messages.length + app.myApprovals.length, 0); assert.equal(aborted, 1); passed++;
  }
  {
    const { app, context } = setup();
    let finish;
    context.fetch = () => new Promise(resolve => { finish = resolve; });
    const pending = app.api('/synthetic'); app.doLogout(); app.token = 'different-login';
    finish({ status: 401 });
    await assert.rejects(pending);
    assert.equal(app.token, 'different-login'); passed++;
  }
  {
    const { app } = setup();
    const states = ['executing', 'execution_failed', 'execution_unknown', 'compensated', 'compensation_failed'];
    for (const state of states) {
      assert.notEqual(app.statusLabel(state), app.statusLabel('executed'));
      assert.notEqual(app.statusClass(state), app.statusClass('executed'));
    }
    assert.equal(app.statusLabel('executed'), '执行成功');
    passed++;
  }
  console.log(`PASS: ${passed} browser-script cases (VM only; real DOM/browser acceptance BLOCKED)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
