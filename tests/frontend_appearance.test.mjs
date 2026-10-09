import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import vm from "node:vm";

test("opaque frontend appearance bridge trusts only its parent and versioned cosmetic snapshots", () => {
  const values = new Map();
  const classes = new Set();
  let listener;
  const parent = { postMessage: message => assert.equal(message.method, "plugin.theme") };
  const root = { style: { setProperty: (key, value) => values.set(key, value) }, dataset: {},
    classList: { toggle: (key, value) => value ? classes.add(key) : classes.delete(key) } };
  vm.runInNewContext(readFileSync(new URL("../sdk/frontend_appearance.js", import.meta.url), "utf8"), {
    crypto: { randomUUID: () => "request" }, document: { documentElement: root },
    window: { parent, addEventListener: (type, callback) => { if (type === "message") listener = callback; } },
  });
  const appearance = { api_contract_version: "1.1.0", mode: "dark", high_contrast: true,
    tokens: { "--ui-bg": "#123456", "unrelated": "hidden" } };
  listener({ source: {}, data: { type: "plugin-appearance-changed", appearance } });
  assert.equal(values.size, 0);
  listener({ source: parent, data: { type: "plugin-appearance-changed", appearance: { ...appearance, api_contract_version: "1.0.0" } } });
  assert.equal(values.size, 0);
  listener({ source: parent, data: { type: "plugin-appearance-changed", appearance } });
  assert.equal(values.get("--ui-bg"), "#123456");
  assert.equal(values.has("unrelated"), false);
  assert.equal(root.dataset.theme, "dark");
  assert.equal(classes.has("high-contrast"), true);
  listener({ source: parent, data: { type: "plugin-api-response", requestId: "request", result: { ...appearance, mode: "light" } } });
  assert.equal(root.dataset.theme, "light");
});

test("sandbox forwards remapped active combinations and respects an empty binding snapshot", () => {
  const events = new Map(), messages = [];
  const parent = { postMessage: message => messages.push(message) };
  const root = { style: { setProperty() {} }, dataset: {}, classList: { toggle() {} } };
  vm.runInNewContext(readFileSync(new URL("../sdk/frontend_appearance.js", import.meta.url), "utf8"), {
    crypto: { randomUUID: () => "request" }, document: { documentElement: root },
    window: { parent, addEventListener: (type, callback) => events.set(type, callback) },
  });
  const apply = keyboard_shortcuts => events.get("message")({ source: parent, data: { type: "plugin-appearance-changed",
    appearance: { api_contract_version: "1.1.0", mode: "light", tokens: {}, navigation_shortcuts: ["g"], keyboard_shortcuts } } });
  const key = changes => { let prevented = false; events.get("keydown")({ key: "g", code: "KeyG", ctrlKey: false,
    metaKey: false, altKey: true, shiftKey: false, getModifierState: () => false,
    preventDefault: () => { prevented = true; }, ...changes }); return prevented; };
  apply([{ id: "nav.g", key: "Alt+Shift+G" }, { id: "app.search", key: "CtrlOrMeta+J" }]);
  assert.equal(key({}), false);
  assert.equal(key({ shiftKey: true }), true);
  assert.equal(messages.at(-1).payload.id, "nav.g");
  assert.equal(messages.at(-1).payload.key, "Alt+Shift+G");
  assert.equal(key({ key: "j", altKey: false, metaKey: true }), true);
  assert.equal(messages.at(-1).payload.id, "app.search");
  assert.equal(key({ key: "j", altKey: false, metaKey: true, ctrlKey: true }), false);
  assert.equal(key({ shiftKey: true, target: { isContentEditable: true } }), false);
  apply([]);
  assert.equal(key({}), false, "Disabled host keys do not fall back to old snapshot hints");
});

test("opaque frame reports intrinsic content sizing without repeating unchanged requests", () => {
  const messages = [];
  let measure, height = 1200;
  const body = { getBoundingClientRect: () => ({ height }) };
  vm.runInNewContext(readFileSync(new URL("../sdk/frontend_appearance.js", import.meta.url), "utf8"), {
    crypto: { randomUUID: () => "request" }, document: { body },
    ResizeObserver: class { constructor(callback) { measure = callback; } observe(value) { assert.equal(value, body); } },
    window: { parent: { postMessage: message => messages.push(message) }, addEventListener() {} },
  });
  measure(); measure(); height = 800.3; measure();
  assert.equal(messages.filter(message => message.method === "plugin.resize").length, 2);
  assert.equal(messages.at(-1).payload.height, 801);
});

test("inline delivery starts frame measurement after the body is ready", () => {
  const events = new Map(), document = {}, messages = [];
  let measure;
  vm.runInNewContext(readFileSync(new URL("../sdk/frontend_appearance.js", import.meta.url), "utf8"), {
    crypto: { randomUUID: () => "request" }, document,
    ResizeObserver: class { constructor(callback) { measure = callback; } observe(value) { assert.equal(value, document.body); } },
    window: { parent: { postMessage: message => messages.push(message) }, addEventListener: (type, callback) => events.set(type, callback) },
  });
  assert.equal(measure, undefined);
  document.body = { getBoundingClientRect: () => ({ height: 1000 }) };
  events.get("DOMContentLoaded")(); measure();
  assert.equal(messages.at(-1).method, "plugin.resize"); assert.equal(messages.at(-1).payload.height, 1000);
});

test("HTTP previews without randomUUID still correlate cosmetic responses", () => {
  const messages = [], values = new Map();
  const parent = { postMessage: message => messages.push(message) };
  let listener;
  vm.runInNewContext(readFileSync(new URL("../sdk/frontend_appearance.js", import.meta.url), "utf8"), {
    crypto: {}, document: { documentElement: { style: { setProperty: (key, value) => values.set(key, value) }, dataset: {}, classList: { toggle() {} } } },
    window: { parent, addEventListener: (type, callback) => { if (type === "message") listener = callback; } },
  });
  assert.match(messages[0].requestId, /^appearance-/);
  listener({ source: parent, data: { type: "plugin-api-response", requestId: messages[0].requestId,
    result: { api_contract_version: "1.1.0", mode: "light", tokens: { "--ui-bg": "#ffffff" } } } });
  assert.equal(values.get("--ui-bg"), "#ffffff");
});


test("opaque frame forwards only host-advertised Alt navigation and protects editing", () => {
  const events = new Map(), messages = [];
  const parent = { postMessage: message => messages.push(message) };
  const root = { style: { setProperty() {} }, dataset: {}, classList: { toggle() {} } };
  vm.runInNewContext(readFileSync(new URL("../sdk/frontend_appearance.js", import.meta.url), "utf8"), {
    crypto: { randomUUID: () => "request" }, document: { documentElement: root },
    window: { parent, addEventListener: (type, callback) => events.set(type, callback) },
  });
  const appearance = { api_contract_version: "1.1.0", mode: "dark", tokens: {}, navigation_shortcuts: ["u", "g"] };
  const key = (changes = {}) => { let prevented = false; const event = { key: "u", code: "KeyU", altKey: true,
    getModifierState: () => false, preventDefault: () => { prevented = true; }, ...changes };
    events.get("keydown")(event); return prevented; };
  assert.equal(key(), false, "No shortcuts before the host snapshot");
  events.get("message")({ source: {}, data: { type: "plugin-appearance-changed", appearance } });
  assert.equal(key(), false, "Other windows cannot advertise shortcuts");
  events.get("message")({ source: parent, data: { type: "plugin-appearance-changed", appearance } });
  assert.equal(key(), true);
  assert.equal(messages.at(-1).method, "plugin.shortcut"); assert.equal(messages.at(-1).payload.key, "u");
  assert.equal(key({ key: "symbol", code: "KeyG" }), true, "Option key uses its underlying code");
  assert.equal(messages.at(-1).payload.key, "g");
  const count = messages.length;
  for (const change of [{ key: "x", code: "KeyX" }, { ctrlKey: true }, { metaKey: true }, { shiftKey: true },
    { repeat: true }, { isComposing: true }, { defaultPrevented: true }, { getModifierState: () => true },
    { target: { closest: () => ({}) } }, { target: { isContentEditable: true } }]) assert.equal(key(change), false);
  assert.equal(messages.length, count);
  assert.equal(key({ key: "?", code: "Slash", altKey: false }), false, "Older snapshots do not advertise host dialogs");
  events.get("message")({ source: parent, data: { type: "plugin-appearance-changed", appearance: { ...appearance, global_shortcuts: ["help", "search", "arbitrary"] } } });
  assert.equal(key({ key: "?", code: "Slash", altKey: false, shiftKey: true }), true);
  assert.equal(messages.at(-1).payload.key, "help");
  for (const modifier of ["ctrlKey", "metaKey"]) {
    assert.equal(key({ key: "k", code: "KeyK", altKey: false, [modifier]: true }), true);
    assert.equal(messages.at(-1).payload.key, "search");
  }
  for (const changes of [{ target: { closest: () => ({}) } }, { altKey: true }, { isComposing: true }, { shiftKey: true }]) {
    assert.equal(key({ key: "k", code: "KeyK", altKey: false, ctrlKey: true, ...changes }), false);
  }
});

for (const version of ["1.1.0", "1.1.1", "1.1.2"]) {
  test(`appearance applies supported contract ${version} in replies and updates`, () => {
    const values = new Map();
    const parent = { postMessage() {} };
    const root = { style: { setProperty: (key, value) => values.set(key, value) },
      dataset: {}, classList: { toggle() {} } };
    let listener;
    vm.runInNewContext(readFileSync(new URL("../sdk/frontend_appearance.js", import.meta.url), "utf8"), {
      crypto: { randomUUID: () => "request" }, document: { documentElement: root },
      window: { parent, addEventListener: (type, callback) => { if (type === "message") listener = callback; } },
    });
    const appearance = { api_contract_version: version, mode: "dark", tokens: { "--ui-bg": "#123456" } };
    listener({ source: parent, data: { type: "plugin-api-response", requestId: "request", result: appearance } });
    assert.equal(root.dataset.theme, "dark");
    assert.equal(values.get("--ui-bg"), "#123456");
    listener({ source: parent, data: { type: "plugin-appearance-changed", appearance: {
      ...appearance, mode: "light", tokens: { "--ui-bg": "#ffffff" },
    } } });
    assert.equal(root.dataset.theme, "light");
    assert.equal(values.get("--ui-bg"), "#ffffff");
  });
}
