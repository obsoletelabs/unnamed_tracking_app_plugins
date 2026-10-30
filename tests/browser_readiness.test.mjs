import assert from "node:assert/strict";
import test from "node:test";
import { gotoWhenReady, waitForServer } from "../tools/browser_readiness.mjs";

test("waitForServer resolves once the server starts answering", async () => {
  let calls = 0;
  await waitForServer("http://x", {
    intervalMs: 1,
    fetchImpl: async () => {
      if (++calls < 3) throw new Error("connection refused");
      return { ok: true };
    },
  });
  assert.equal(calls, 3);
});

test("waitForServer fails loudly instead of continuing against a dead server", async () => {
  await assert.rejects(
    waitForServer("http://x", { timeoutMs: 20, intervalMs: 1, fetchImpl: async () => ({ ok: false, status: 503 }) }),
    /not ready after 20ms \(HTTP 503\)/,
  );
});

function fakePage(rendersOnAttempt) {
  const log = [];
  let attempt = 1;
  return {
    log,
    goto: async url => log.push(`goto ${url}`),
    reload: async () => { attempt += 1; log.push("reload"); },
    ready: () => ({
      waitFor: async ({ timeout }) => {
        log.push(`wait ${timeout}`);
        if (attempt < rendersOnAttempt) {
          const error = new Error("timeout");
          error.name = "TimeoutError";
          throw error;
        }
      },
    }),
  };
}

test("gotoWhenReady reloads once when a cold first render is lost", async () => {
  const page = fakePage(2);
  await gotoWhenReady(page, "http://app/page", page.ready, { firstWaitMs: 1, finalWaitMs: 2 });
  assert.deepEqual(page.log, ["goto http://app/page", "wait 1", "reload", "wait 2"]);
});

test("gotoWhenReady still fails when the page never renders", async () => {
  const page = fakePage(99);
  await assert.rejects(gotoWhenReady(page, "http://app/page", page.ready, { firstWaitMs: 1, finalWaitMs: 2 }), /timeout/);
  assert.equal(page.log.filter(entry => entry === "reload").length, 1);
});

test("gotoWhenReady does not mask unrelated errors with a reload", async () => {
  const page = { goto: async () => { throw new Error("net::ERR_CONNECTION_REFUSED"); } };
  await assert.rejects(gotoWhenReady(page, "http://app", () => ({}), {}), /ERR_CONNECTION_REFUSED/);
});
