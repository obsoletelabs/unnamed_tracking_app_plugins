import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../official/jellyfin-media-sync/native/app.js", import.meta.url), "utf8");
const { activate } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const flush = () => new Promise(resolve => setImmediate(resolve));
function h(tag, props, children) {
  if (children === undefined && (Array.isArray(props) || typeof props === "string")) return { tag, props: {}, children: props };
  return { tag, props: props || {}, children };
}
function all(tree) {
  return tree && typeof tree === "object" ? [tree, ...[tree.children].flat(Infinity).flatMap(all)] : [];
}
function fixture(admin = false, nativePassword = false) {
  const PasswordInput = { name: "PasswordInput" };
  const components = {}, cleanup = [], unmount = [], calls = [], timers = new Map(), timerDelays = new Map();
  const original = [global.setTimeout, global.clearTimeout, Date.now];
  const delays = [], clock = { now: Date.now() };
  let nextTimer = 0;
  global.setTimeout = (fn, delay) => { const id = ++nextTimer; timers.set(id, fn); timerDelays.set(id, delay); delays.push(delay); return id; };
  global.clearTimeout = id => timers.delete(id);
  Date.now = () => clock.now;
  const config = { is_admin: admin, host_user_id: "owned-user", review_total: 1,
    servers: [{ id: "server", name: "Fixture", enabled: true, libraries: [{ id: "library", name: "Films" }], users: [], mappings: { library: "movie" } }],
    accounts: [{ id: "account", server_id: "server", name: "Viewer", libraries: [], enabled: true, background_sync: false }],
    reviews: [{ account_id: "account", external_id: "item", title: "Remapped show", reason: "category_changed", media_type: "tv_show", host_id: "media", candidates: [] }] };
  const host = { async runAction(id, values = {}) {
    calls.push([id, values]);
    return id === "get-config" ? config : id === "status" ? { accounts: { account: { phase: "idle", reviews: config.review_total } } } : { ok: true };
  } };
  activate({ version: "0.0.2", ui: nativePassword ? { PasswordInput } : {}, vue: { h, ref: value => ({ value }), reactive: x => x, defineComponent: x => x, onBeforeUnmount: fn => unmount.push(fn) },
    registerComponent: (id, component) => { components[id] = component; }, onCleanup: fn => cleanup.push(fn) });
  return { components, host, config, calls, timers, timerDelays, clock, delays, unmount, PasswordInput, close() {
    cleanup.forEach(fn => fn());
    [global.setTimeout, global.clearTimeout, Date.now] = original;
  } };
}

test("User page separates administration, uses installed version and clears password immediately", async () => {
  const f = fixture(true);
  try {
    const render = f.components.accounts.setup({ host: f.host });
    await flush();
    assert(!all(render()).some(x => x.props["data-testid"] === "jf-admin"));
    assert(JSON.stringify(render()).includes("Official preview · 0.0.2"));
    const password = all(render()).find(x => x.tag === "input" && x.props.type === "password");
    password.props.onInput({ target: { value: "DisposablePassword" } });
    all(render()).find(x => x.tag === "button" && x.children === "Sign in").props.onClick();
    assert.equal(f.calls.find(x => x[0] === "login")[1].password, "DisposablePassword");
    assert.equal(all(render()).find(x => x.tag === "input" && x.props.type === "password").props.value, "");
    await flush();
  } finally { f.close(); }
});

test("Unnumbered recordings require an explicit real episode mapping", async () => {
  const f = fixture();
  try {
    f.config.reviews = [{ account_id: "account", external_id: "episode", title: "Recording",
      reason: "missing_episode_number", parent_external_id: "series", candidates: [] }];
    const render = f.components.accounts.setup({ host: f.host });
    await flush();
    assert(!all(render()).some(x => x.tag === "button" && x.children === "Create separate entry"));
    const inputs = all(render()).filter(x => x.tag === "input" && x.props.type === "number");
    assert.equal(inputs.length, 2);
    inputs[0].props.onInput({ target: { value: "0" } });
    inputs[1].props.onInput({ target: { value: "7" } });
    all(render()).find(x => x.tag === "button" && x.children === "Assign episode number").props.onClick();
    const values = f.calls.find(x => x[0] === "resolve-review")[1];
    assert.equal(values.decision, "map_episode");
    assert.equal(values.season, 0);
    assert.equal(values.number, 7);
  } finally { f.close(); }
});

test("Administrator page is separate and regular users cannot see discovery controls", async () => {
  const f = fixture(false);
  try {
    const render = f.components.admin.setup({ host: f.host });
    await flush();
    assert(JSON.stringify(render()).includes("Administrator access is required"));
    assert(!all(render()).some(x => x.tag === "input"));
    assert.equal(f.timers.size, 0);
  } finally { f.close(); }
});

test("Administrator loading never presents an access denial before the host responds", async () => {
  const f = fixture(true);
  try {
    let resolve;
    f.host.runAction = () => new Promise(done => { resolve = done; });
    const render = f.components.admin.setup({ host: f.host });
    assert(JSON.stringify(render()).includes("Loading Jellyfin configuration"));
    assert(!JSON.stringify(render()).includes("Administrator access is required"));
    resolve(f.config); await flush();
    assert(all(render()).some(x => x.props["data-testid"] === "jf-admin"));
    assert(!JSON.stringify(render()).includes("Administrator access is required"));
  } finally { f.close(); }
});

test("Failed configuration explains missing access and can be retried without reloading", async () => {
  const f = fixture(true);
  try {
    f.host.runAction = async () => { throw new Error("Plugin action failed (403): Review plugin.storage approval in Plugin Manager."); };
    const render = f.components.admin.setup({ host: f.host }); await flush();
    assert(JSON.stringify(render()).includes("plugin.storage approval"));
    assert(!JSON.stringify(render()).includes("Administrator access is required"));
    assert(!all(render()).some(x => x.tag === "input"));
    f.host.runAction = async () => f.config;
    await all(render()).find(x => x.tag === "button" && x.children === "Retry loading").props.onClick();
    assert(all(render()).some(x => x.props["data-testid"] === "jf-admin"));
    assert(!JSON.stringify(render()).includes("plugin.storage approval"));
  } finally { f.close(); }
});

test("Account actions retain the host's error instead of reporting an administrator denial", async () => {
  const f = fixture();
  try {
    const render = f.components.accounts.setup({ host: f.host }); await flush();
    f.host.runAction = async () => { throw new Error("Plugin action failed (503): Runtime unavailable. Retry when ready."); };
    await all(render()).find(x => x.tag === "button" && x.children === "Sign in").props.onClick();
    assert(JSON.stringify(render()).includes("Runtime unavailable. Retry when ready."));
  } finally { f.close(); }
});

test("Polling refreshes review decisions without overwriting unsaved account preferences", async () => {
  const f = fixture();
  try {
    const render = f.components.accounts.setup({ host: f.host });
    await flush();
    const automatic = all(render()).find(x => x.tag === "label" && String(x.children).includes("Automatic sync"));
    all(automatic).find(x => x.tag === "input").props.onChange({ target: { checked: true } });
    const poll = [...f.timers.values()][0]; f.timers.clear();
    await poll();
    all(render()).find(x => x.tag === "button" && x.children === "Save preferences").props.onClick();
    assert.equal(f.calls.find(x => x[0] === "save-account")[1].background_sync, true);
    await flush();
    all(render()).find(x => x.tag === "button" && x.children === "Keep existing category").props.onClick();
    assert.equal(f.calls.find(x => x[0] === "resolve-review")[1].decision, "keep_category");
    await flush();
    f.unmount.forEach(fn => fn());
    assert.equal(f.timers.size, 0);
  } finally { f.close(); }
});


test("Shared native password box updates and clears Jellyfin secrets", async () => {
  const f = fixture(true, true);
  try {
    const render = f.components.accounts.setup({ host: f.host }); await flush();
    const password = () => all(render()).find(x => x.tag === f.PasswordInput);
    assert.equal(password().props.inputAriaLabel, "Password");
    password().props["onUpdate:modelValue"]("DisposableSecret");
    all(render()).find(x => x.tag === "button" && x.children === "Sign in").props.onClick();
    assert.equal(f.calls.find(x => x[0] === "login")[1].password, "DisposableSecret");
    assert.equal(password().props.modelValue, "");
  } finally { f.close(); }
});


test("idle polls avoid full configuration reads and hidden pages pause requests", async () => {
  const f = fixture();
  const originalDocument = global.document;
  try {
    f.components.accounts.setup({ host: f.host }); await flush();
    assert.equal(f.calls.filter(([id]) => id === "get-config").length, 1);
    assert.equal(f.delays.at(-1), 30000);
    const tick = async () => { const fn = [...f.timers.values()][0]; f.timers.clear(); await fn(); };
    await tick();
    assert.equal(f.calls.filter(([id]) => id === "get-config").length, 1);
    const before = f.calls.length;
    global.document = { hidden: true };
    await tick();
    assert.equal(f.calls.length, before);
    global.document = { hidden: false };
    f.host.runAction = async (id) => {
      f.calls.push([id, {}]);
      return id === "status" ? { accounts: { account: { phase: "syncing", reviews: 2 } } } : f.config;
    };
    await tick();
    assert.equal(f.calls.filter(([id]) => id === "get-config").length, 2);
    assert.equal(f.delays.at(-1), 5000);
  } finally {
    if (originalDocument === undefined) delete global.document;
    else global.document = originalDocument;
    f.close();
  }
});


const START = { ok: true, state: "pending", pending_id: "pending", code: "123456", expires_in: 300, poll_seconds: 2 };
const WAITING = { ok: false, pending: true, state: "pending", expires_in: 250, message: "Waiting for approval in Jellyfin." };
const APPROVED = { ok: true, state: "authorized", account_id: "account", message: "Account connected." };

async function openQuickConnect(f, finish, start = START) {
  const render = f.components.accounts.setup({ host: f.host }); await flush();
  f.host.runAction = async (id, values = {}) => {
    f.calls.push([id, values]);
    if (id === "get-config") return f.config;
    if (id === "status") return { accounts: {} };
    if (id === "quick-connect-start") return start;
    if (id === "quick-connect-finish") return finish(values);
    return { ok: true };
  };
  const button = label => all(render()).find(x => x.tag === "button" && x.children === label);
  await button("Quick Connect").props.onClick();
  const panel = () => all(render()).find(x => x.props["data-testid"] === "jf-quick-connect");
  // The quick timer is the only 2s one; the status poll uses 1s, 5s or 30s.
  const timer = () => [...f.timers].find(([id]) => f.timerDelays.get(id) === 2000);
  const finishes = () => f.calls.filter(([id]) => id === "quick-connect-finish");
  const fire = async () => { const [id, fn] = timer(); f.timers.delete(id); await fn(); await flush(); };
  return { render, button, panel, timer, finishes, fire, text: () => JSON.stringify(panel() || null) };
}

test("Quick Connect checks by itself and connects when Jellyfin reports the code approved", async () => {
  const f = fixture();
  try {
    const answers = [WAITING, WAITING, APPROVED];
    const q = await openQuickConnect(f, () => answers.shift());
    assert.equal(q.panel().props["data-state"], "waiting");
    assert(q.text().includes("123456") && q.text().includes("checks automatically"));
    assert(q.timer(), "a check is scheduled without any button press");
    assert.equal(q.finishes().length, 0);
    await q.fire();
    await q.fire();
    assert.equal(q.finishes().length, 2);
    assert.equal(q.panel().props["data-state"], "waiting");
    const configReads = f.calls.filter(([id]) => id === "get-config").length;
    await q.fire();
    assert.equal(q.finishes().length, 3);
    assert(q.finishes().every(([, values]) => values.pending_id === "pending" && Object.keys(values).length === 1));
    assert.equal(q.panel().props["data-state"], "authorized");
    assert(q.text().includes("Account connected."));
    assert.equal(q.timer(), undefined, "polling stops on success");
    assert.equal(f.calls.filter(([id]) => id === "get-config").length, configReads + 1, "accounts are reloaded");
  } finally { f.close(); }
});

test("Quick Connect never overlaps checks and Check now is a manual fallback", async () => {
  const f = fixture();
  try {
    let release;
    const q = await openQuickConnect(f, () => new Promise(done => { release = done; }));
    const [id, fn] = q.timer(); f.timers.delete(id);
    const running = fn();
    assert.equal(q.finishes().length, 1);
    await q.button("Check now").props.onClick();
    assert.equal(q.finishes().length, 1, "no second request while one is in flight");
    assert.equal(q.timer(), undefined, "the next check is armed only after the reply");
    release(WAITING); await running; await flush();
    assert(q.timer());
    // Check now does not wait for the timer.
    const manual = q.button("Check now").props.onClick();
    assert.equal(q.finishes().length, 2);
    release(APPROVED); await manual; await flush();
    assert.equal(q.panel().props["data-state"], "authorized");
    assert.equal(q.timer(), undefined);
  } finally { f.close(); }
});

test("Quick Connect stops when the code expires, by Jellyfin or by the clock", async () => {
  const f = fixture();
  try {
    const q = await openQuickConnect(f, () => ({ ok: false, state: "expired", message: "Quick Connect expired. Start a new connection." }));
    await q.fire();
    assert.equal(q.panel().props["data-state"], "expired");
    assert.equal(q.timer(), undefined);
    assert(q.button("Get a new code"));
    assert(!q.button("Check now"));
  } finally { f.close(); }
  const g = fixture();
  try {
    const q = await openQuickConnect(g, () => WAITING);
    g.clock.now += 301 * 1000;
    await q.fire();
    assert.equal(q.finishes().length, 0, "an expired code is not sent to Jellyfin");
    assert.equal(q.panel().props["data-state"], "expired");
    assert.equal(q.timer(), undefined);
  } finally { g.close(); }
});

test("Quick Connect retries brief failures, then reports the error and offers a way forward", async () => {
  const f = fixture();
  try {
    const q = await openQuickConnect(f, () => ({ ok: false, state: "error", retryable: true, message: "Jellyfin is unavailable." }));
    await q.fire(); await q.fire();
    assert.equal(q.panel().props["data-state"], "waiting", "two blips are tolerated");
    await q.fire();
    assert.equal(q.finishes().length, 3);
    assert.equal(q.panel().props["data-state"], "error");
    assert(q.text().includes("Jellyfin is unavailable."));
    assert.equal(q.timer(), undefined);
    assert(q.button("Check now") && q.button("Get a new code"));
    f.host.runAction = async (id, values = {}) => { f.calls.push([id, values]); return id === "get-config" ? f.config : APPROVED; };
    await q.button("Check now").props.onClick();
    assert.equal(q.panel().props["data-state"], "authorized");
  } finally { f.close(); }
  const g = fixture();
  try {
    const q = await openQuickConnect(g, () => { throw new Error("Plugin action failed (503): Runtime unavailable."); });
    await q.fire(); await q.fire(); await q.fire();
    assert.equal(q.panel().props["data-state"], "error");
    assert(q.text().includes("Runtime unavailable."));
  } finally { g.close(); }
  const h2 = fixture();
  try {
    const q = await openQuickConnect(h2, () => ({ ok: false, state: "error", retryable: false, message: "The server changed." }));
    await q.fire();
    assert.equal(q.panel().props["data-state"], "error");
    assert.equal(q.finishes().length, 1, "a permanent failure is not retried");
  } finally { h2.close(); }
});

test("Quick Connect stops on unmount and ignores a reply that arrives afterwards", async () => {
  const f = fixture();
  try {
    let release;
    const q = await openQuickConnect(f, () => new Promise(done => { release = done; }));
    const [id, fn] = q.timer(); f.timers.delete(id);
    const running = fn();
    f.unmount.forEach(stop => stop());
    release(APPROVED); await running; await flush();
    assert.equal(f.timers.size, 0);
    assert.equal(f.calls.filter(([call]) => call === "get-config").length, 1, "no reload after unmount");
  } finally { f.close(); }
  const g = fixture();
  try {
    const q = await openQuickConnect(g, () => WAITING);
    assert(q.timer());
    g.unmount.forEach(stop => stop());
    assert.equal(g.timers.size, 0);
  } finally { g.close(); }
});

test("A new code supersedes the old one and Cancel stops checking", async () => {
  const f = fixture();
  try {
    let release;
    const q = await openQuickConnect(f, () => new Promise(done => { release = done; }));
    const [id, fn] = q.timer(); f.timers.delete(id);
    const stale = fn();
    await q.button("Quick Connect").props.onClick();
    release(APPROVED); await stale; await flush();
    assert.equal(q.panel().props["data-state"], "waiting", "a stale reply cannot complete the new request");
    await q.button("Cancel").props.onClick();
    assert.equal(q.panel(), undefined);
    assert.equal(q.timer(), undefined);
  } finally { f.close(); }
});

test("A Quick Connect that cannot start and a refused password show the reason from Jellyfin", async () => {
  const f = fixture();
  try {
    const q = await openQuickConnect(f, () => WAITING, { ok: false, state: "error", message: "Quick Connect is disabled on this Jellyfin server." });
    assert.equal(q.panel(), undefined);
    assert.equal(q.timer(), undefined);
    assert(JSON.stringify(q.render()).includes("Quick Connect is disabled on this Jellyfin server."));
    f.host.runAction = async id => id === "login"
      ? { ok: false, state: "error", message: "Jellyfin rejected that username or password." }
      : f.config;
    await q.button("Sign in").props.onClick();
    assert(JSON.stringify(q.render()).includes("Jellyfin rejected that username or password."));
  } finally { f.close(); }
});

test("The only enabled server is selected so sign-in does not depend on a hidden choice", async () => {
  const f = fixture();
  try {
    const render = f.components.accounts.setup({ host: f.host }); await flush();
    all(render()).find(x => x.tag === "button" && x.children === "Sign in").props.onClick();
    assert.equal(f.calls.find(x => x[0] === "login")[1].server_id, "server");
  } finally { f.close(); }
  const g = fixture();
  try {
    g.config.servers.push({ ...g.config.servers[0], id: "second", name: "Second" });
    const render = g.components.accounts.setup({ host: g.host }); await flush();
    all(render()).find(x => x.tag === "button" && x.children === "Sign in").props.onClick();
    assert.equal(g.calls.find(x => x[0] === "login")[1].server_id, "", "two servers still require a choice");
  } finally { g.close(); }
});
