const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "../official/epic-games/frontend");
const asset = (name) => fs.readFileSync(
  name.startsWith("appearance.")
    ? path.resolve(__dirname, "../sdk", `frontend_${name}`)
    : path.join(root, name), "utf8",
);
const html = fs.readFileSync(path.join(root, "index.html"), "utf8")
  .replace(/<link rel="stylesheet" href="\.\/([^"]+)">/g,
    (_, name) => `<style>${asset(name)}</style>`)
  .replace(/<script src="\.\/([^"]+)"><\/script>/g,
    (_, name) => `<script nonce="fixture">${asset(name).replace(/<\/script/gi, "<\\/script")}</script>`)
  .replace("<head>", `<head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-fixture'; style-src 'unsafe-inline'">`);
let browser;
before(async () => { browser = await chromium.launch({ args: ["--no-sandbox"] }); });
after(async () => { await browser?.close(); });

async function mount(page, signinUrl = "https://www.epicgames.com/id/login?fixture=1", menuSync = false, startConnected = false) {
  await page.evaluate(({ markup, signinUrl, menuSync, startConnected }) => {
    const iframe = document.querySelector("iframe");
    window.actions = [];
    window.addEventListener("message", event => {
      if (event.source !== iframe.contentWindow || event.data?.type !== "plugin-api-request") return;
      const { payload, requestId } = event.data;
      let result = {};
      if (event.data.method === "plugin.context") result = { initial_action_id: menuSync ? "sync" : "" };
      if (event.data.method === "plugin.run-action") {
        window.actions.push({ action: payload.actionId, code: payload.values.authorization_code });
        if (payload.actionId === "status") result = { connected: Boolean(menuSync || startConnected), display_name: "Fixture player", phase: "idle", login_url: signinUrl };
        else if (payload.actionId === "start") result = { ok: false, error: "Epic rejected this sign-in. Sign in on Epic again and paste a fresh code." };
        else if (menuSync && ["sync", "step"].includes(payload.actionId)) result = { connected: true, display_name: "Fixture player", phase: payload.actionId === "sync" && menuSync !== "complete" ? "playtime" : "complete", imported: 1 };
        else if (payload.actionId === "signin") {
          result = { redirect_url: signinUrl };
          window.setTimeout(() => window.location.assign(signinUrl), 0);
        } else if (String(payload.values.authorization_code || "").includes("b".repeat(32))) result = { connected: true, display_name: "Fixture player", phase: "idle" };
        else result = { ok: false, error: "Paste a valid one-time code." };
      }
      event.source.postMessage({ type: "plugin-api-response", requestId, result }, "*");
    });
    iframe.srcdoc = markup;
  }, { markup: html, signinUrl, menuSync, startConnected });
}

test("a connected account can replace an expired sign-in without disconnecting", async () => {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(String(error)));
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts"></iframe>');
    await mount(page, "https://www.epicgames.com/id/login?fixture=1", false, true);
    const frame = page.frameLocator("iframe");
    await frame.getByText("Connected as Fixture player.", { exact: true }).waitFor();
    assert.equal(await frame.locator("#connect-panel").isVisible(), false);
    // An import that finds the sign-in expired offers the code field in place.
    await frame.getByRole("button", { name: "Import games" }).click();
    await frame.getByText("Epic rejected this sign-in. Sign in on Epic again and paste a fresh code.", { exact: true }).waitFor();
    assert.equal(await frame.locator("#connect-panel").isVisible(), true);
    // Pasting Epic's page connects without another click.
    await frame.locator("#code").evaluate(input => {
      input.value = JSON.stringify({ redirectUrl: "https://localhost/?code=" + "b".repeat(32), authorizationCode: "b".repeat(32) });
      input.dispatchEvent(new Event("paste"));
    });
    await frame.locator("#error").waitFor({ state: "hidden" });
    await page.waitForFunction(() => window.actions.some(item => item.action === "connect"));
    assert.equal(await frame.locator("#connect-panel").isVisible(), false);
    assert.equal(await frame.getByRole("button", { name: "Replace sign-in" }).isVisible(), true);
    assert.deepEqual(errors, []);
  } finally { await page.close(); }
});

test("a connected account does not see sign-in controls while status loads", async () => {
  const page = await browser.newPage();
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts"></iframe>');
    // No host response yet: the frame must keep its neutral loading state.
    await page.evaluate(markup => { document.querySelector("iframe").srcdoc = markup; }, html);
    const frame = page.frameLocator("iframe");
    await frame.getByText("Checking connection…", { exact: true }).waitFor();
    assert.equal(await frame.locator("#connect-panel").isVisible(), false);
    assert.equal(await frame.locator("#import-panel").isVisible(), false);
  } finally { await page.close(); }
});

test("opaque sandbox connects through clicks and Enter, clearing codes and showing safe errors", async () => {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(String(error)));
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts"></iframe>');
    await mount(page);
    const frame = page.frameLocator("iframe");
    await frame.getByText("Connect your Epic account to start.", { exact: true }).waitFor();
    assert.equal(await frame.locator("#import-panel").isVisible(), false);
    await frame.getByLabel("Epic authorization code").fill("invalid");
    await frame.getByRole("button", { name: "Connect Epic", exact: true }).click();
    await frame.getByText("Paste a valid one-time code.", { exact: true }).waitFor();
    assert.equal(await frame.getByLabel("Epic authorization code").inputValue(), "");
    await frame.getByLabel("Epic authorization code").fill("b".repeat(32));
    await frame.getByLabel("Epic authorization code").press("Enter");
    await frame.getByText("Connected as Fixture player.", { exact: true }).waitFor();
    assert.equal(await frame.locator("#import-panel").isVisible(), true);
    assert.equal(await frame.getByLabel("Epic authorization code").inputValue(), "");
    assert.equal(await frame.locator("#error").isVisible(), false);
    assert.deepEqual(await page.evaluate(() => window.actions.filter(item => item.action === "connect")), [
      { action: "connect", code: "invalid" }, { action: "connect", code: "b".repeat(32) },
    ]);
    assert.deepEqual(errors, []);
  } finally { await page.close(); }
});

test("a Games-menu sync opens the connected view and continues the existing import flow", async () => {
  const page = await browser.newPage();
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts"></iframe>');
    await mount(page, "https://www.epicgames.com/id/login?fixture=1", true);
    const frame = page.frameLocator("iframe");
    await frame.getByText("Import complete.", { exact: true }).waitFor();
    assert.equal(await frame.locator("#imported").innerText(), "1");
    assert.deepEqual(await page.evaluate(() => window.actions.map(item => item.action)), ["status", "sync", "step"]);
    assert.equal(await frame.locator("#connect-panel").isVisible(), false);
  } finally { await page.close(); }
});

test("a completed menu sync does not immediately start a second import", async () => {
  const page = await browser.newPage();
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts"></iframe>');
    await mount(page, "https://www.epicgames.com/id/login?fixture=1", "complete");
    await page.frameLocator("iframe").getByText("Import complete.", { exact: true }).waitFor();
    assert.deepEqual(await page.evaluate(() => window.actions.map(item => item.action)), ["status", "sync"]);
  } finally { await page.close(); }
});

test("Epic sign-in delegates external navigation to the host without popup privileges", async () => {
  const page = await browser.newPage();
  const signinUrl = "https://www.epicgames.com/id/login?fixture=1";
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts"></iframe>');
    await mount(page, signinUrl);
    const frame = page.frameLocator("iframe");
    await frame.getByRole("button", { name: "Sign in on Epic Games" }).waitFor();
    await frame.getByRole("button", { name: "Sign in on Epic Games" }).click();
    await page.waitForURL(signinUrl, { waitUntil: "commit", timeout: 10000 });
    assert.equal(page.url(), signinUrl);
  } finally { await page.close(); }
});

test("copying the sign-in link retains the page and offers manual copying in an opaque sandbox", async () => {
  for (const width of [320, 390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 1100 } });
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    const signinUrl = "https://www.epicgames.com/id/login?redirectUrl=" + encodeURIComponent(
      "https://www.epicgames.com/id/api/redirect?clientId=34a02cf8f4414e29b15921876da36f9a&responseType=code",
    );
    try {
      await page.setContent('<iframe title="Epic" sandbox="allow-scripts" style="width:100%;height:1000px;border:0"></iframe>');
      await mount(page, signinUrl);
      const frame = page.frameLocator("iframe");
      await frame.getByText("Use your regular browser", { exact: true }).click();
      await frame.getByRole("button", { name: "Copy sign-in link" }).click();
      await frame.getByText("Copy the selected link using your browser's Copy command, then paste it into your regular browser.", { exact: true }).waitFor();
      assert.equal(await frame.getByLabel("Epic sign-in link").inputValue(), signinUrl);
      assert.equal(await frame.getByLabel("Epic sign-in link").getAttribute("readonly"), "");
      assert.equal(page.url(), "about:blank");
      assert.deepEqual(await page.evaluate(() => window.actions.map(item => item.action)), ["status"]);
      assert(await frame.locator("body").evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      if (process.env.EPIC_COPY_SCREENSHOTS) {
        fs.mkdirSync(process.env.EPIC_COPY_SCREENSHOTS, { recursive: true });
        await page.screenshot({ path: path.join(process.env.EPIC_COPY_SCREENSHOTS, `epic-copy-link-${width}.png`), fullPage: true });
      }
      assert.deepEqual(errors, []);
    } finally { await page.close(); }
  }
});
