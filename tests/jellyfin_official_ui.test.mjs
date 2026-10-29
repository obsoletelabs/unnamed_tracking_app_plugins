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
  const components = {}, cleanup = [], unmount = [], calls = [], timers = new Map();
  const original = [global.setTimeout, global.clearTimeout];
  const delays = [];
  global.setTimeout = (fn, delay) => { const id = timers.size + 1; timers.set(id, fn); delays.push(delay); return id; };
  global.clearTimeout = id => timers.delete(id);
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
  return { components, host, config, calls, timers, delays, unmount, PasswordInput, close() {
    cleanup.forEach(fn => fn());
    [global.setTimeout, global.clearTimeout] = original;
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
