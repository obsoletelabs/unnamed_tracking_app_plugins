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

async function mount(page, signinUrl = "https://www.epicgames.com/id/login?fixture=1") {
  await page.evaluate(({ markup, signinUrl }) => {
    const iframe = document.querySelector("iframe");
    window.actions = [];
    window.addEventListener("message", event => {
      if (event.source !== iframe.contentWindow || event.data?.type !== "plugin-api-request") return;
      const { payload, requestId } = event.data;
      let result = {};
      if (event.data.method === "plugin.run-action") {
        window.actions.push({ action: payload.actionId, code: payload.values.authorization_code });
        if (payload.actionId === "status") result = { connected: false, phase: "idle" };
        else if (payload.actionId === "signin") result = { redirect_url: signinUrl };
        else if (payload.values.authorization_code === "b".repeat(32)) result = { connected: true, display_name: "Fixture player", phase: "idle" };
        else result = { ok: false, error: "Paste a valid one-time code." };
      }
      event.source.postMessage({ type: "plugin-api-response", requestId, result }, "*");
    });
    iframe.srcdoc = markup;
  }, { markup: html, signinUrl });
}

test("opaque sandbox connects through clicks and Enter, clearing codes and showing safe errors", async () => {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(String(error)));
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"></iframe>');
    await mount(page);
    const frame = page.frameLocator("iframe");
    await frame.getByText("Connect your Epic account to start.", { exact: true }).waitFor();
    await frame.getByLabel("Epic authorization code").fill("invalid");
    await frame.getByRole("button", { name: "Connect Epic", exact: true }).click();
    await frame.getByText("Paste a valid one-time code.", { exact: true }).waitFor();
    assert.equal(await frame.getByLabel("Epic authorization code").inputValue(), "");
    await frame.getByLabel("Epic authorization code").fill("b".repeat(32));
    await frame.getByLabel("Epic authorization code").press("Enter");
    await frame.getByText("Connected as Fixture player.", { exact: true }).waitFor();
    assert.equal(await frame.getByLabel("Epic authorization code").inputValue(), "");
    assert.equal(await frame.locator("#error").isVisible(), false);
    assert.deepEqual(await page.evaluate(() => window.actions.filter(item => item.action === "connect")), [
      { action: "connect", code: "invalid" }, { action: "connect", code: "b".repeat(32) },
    ]);
    assert.deepEqual(errors, []);
  } finally { await page.close(); }
});

test("Epic sign-in opens a separate tab and leaves the code-entry page available", async () => {
  const page = await browser.newPage();
  try {
    await page.setContent('<iframe title="Epic" sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"></iframe>');
    await mount(page);
    const frame = page.frameLocator("iframe");
    await frame.getByRole("button", { name: "Sign in on Epic Games" }).waitFor();
    const popupPromise = page.waitForEvent("popup");
    await frame.getByRole("button", { name: "Sign in on Epic Games" }).click();
    const popup = await popupPromise;
    await popup.waitForURL("https://www.epicgames.com/id/login?fixture=1", { waitUntil: "commit" });
    await frame.getByLabel("Epic authorization code").fill("code-can-be-pasted-here");
    assert.equal(await frame.getByLabel("Epic authorization code").inputValue(), "code-can-be-pasted-here");
    await popup.close();
  } finally { await page.close(); }
});
