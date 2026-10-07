import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

// The native module is a browser ES module; load its actual packaged source.
const source = await readFile(
  new URL(
    "../examples/self-service-session-manager/native/index.js",
    import.meta.url,
  ),
  "utf8",
);
const {
  createController,
  clusterPoints,
  locationText,
  project,
  sessionDevice,
} = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

test("browser summaries preserve browser precedence and mobile operating systems", () => {
  for (const [agent, expected] of [
    [
      "Mozilla/5.0 (Windows NT 10.0) Chrome/140.0 Safari/537.36 Edg/140.0",
      "Edge on Windows",
    ],
    [
      "Mozilla/5.0 (Linux; Android 16) Chrome/140.0 Safari/537.36",
      "Chrome on Android",
    ],
    ["Mozilla/5.0 (iPhone) Version/18.0 Safari/604.1", "Safari on iOS"],
    ["Mozilla/5.0 (iPad) FxiOS/140.0 Safari/604.1", "Firefox on iOS"],
    ["Mozilla/5.0 (Macintosh) Firefox/140.0", "Firefox on macOS"],
    [null, "Browser unavailable"],
    ["custom-client", "Other browser"],
  ])
    assert.equal(sessionDevice(agent), expected);
});

test("filters and cursor reach the declared scoped action; append preserves all rows", async () => {
  const calls = [];
  const controller = createController(
    {
      runAction: async (action, values) => {
        calls.push([action, values]);
        return {
          sessions: [{ id: String(calls.length) }],
          next_cursor: calls.length === 1 ? "cursor" : null,
        };
      },
    },
    true,
  );
  Object.assign(controller.state.filters, {
    q: "browser",
    country: "Australia",
    anomaly: true,
    user_id: "user",
  });
  await controller.load();
  controller.state.filters.q = "not applied yet";
  await controller.load(true);
  assert.equal(calls[0][0], "list-admin-sessions");
  assert.equal(calls[0][1].anomaly, true);
  assert.equal(calls[0][1].user_id, "user");
  assert.equal(calls[1][1].cursor, "cursor");
  assert.equal(calls[1][1].q, "browser");
  assert.equal(controller.state.sessions.length, 2);
  assert.equal(controller.state.cursor, null);
});

test("cancelling confirmation neither refreshes nor signs out", async () => {
  const calls = [];
  const controller = createController({
    runAction: async (action) => {
      calls.push(action);
      return { cancelled: true };
    },
    navigate: async () => assert.fail("must not navigate"),
  });
  await controller.revoke("revoke-all-sessions", {}, true);
  assert.deepEqual(calls, ["revoke-all-sessions"]);
  assert.equal(controller.state.notice, "");
  assert.equal(controller.state.busy, false);
});

test("bulk current-session revocation signs out without making an unauthorized refresh", async () => {
  const calls = [];
  const controller = createController({
    runAction: async (action) => {
      calls.push(action);
      return { revoked: 3, current_revoked: true };
    },
    navigate: async (path) => calls.push(path),
  });
  await controller.revoke("revoke-user-sessions", { user_id: "own-user" });
  assert.deepEqual(calls, ["revoke-user-sessions", "/login"]);
  assert.match(controller.state.notice, /3 sessions revoked/);
});

test("failed revocation preserves rows and displays the failure", async () => {
  const controller = createController({
    runAction: async () => {
      throw new Error("Permission denied");
    },
  });
  controller.state.sessions = [{ id: "owned" }];
  await controller.revoke("revoke-session", { session_id: "owned" });
  assert.deepEqual(controller.state.sessions, [{ id: "owned" }]);
  assert.equal(controller.state.error, "Permission denied");
});

test("unmount ignores pending read results", async () => {
  let finish;
  const controller = createController({
    runAction: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  const loading = controller.load();
  controller.dispose();
  finish({ sessions: [{ id: "late" }] });
  await loading;
  assert.equal(controller.state.sessions.length, 0);
});

test("map clusters actual coordinates and excludes revoked or unavailable positions", () => {
  const sessions = [
    {
      id: "a",
      state: "active",
      location: { latitude: -31.95, longitude: 115.86 },
    },
    {
      id: "b",
      state: "expired",
      location: { latitude: -31.95, longitude: 115.86 },
    },
    {
      id: "c",
      state: "revoked",
      location: { latitude: -31.95, longitude: 115.86 },
    },
    { id: "d", state: "active", location: { latitude: null, longitude: null } },
  ];
  const clusters = clusterPoints(sessions, 2);
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].sessions.length, 2);
  assert.deepEqual(project(0, 0, 2), { x: 512, y: 512 });
  assert.equal(
    locationText({ location: { network_label: "Private network" } }),
    "Private network",
  );
});
