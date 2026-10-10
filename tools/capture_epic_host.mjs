// Real installed plugin, host actions and database; Epic responses use HTTP fixtures.
import assert from "node:assert/strict";
import { createServer, request as httpRequest } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const [pluginsRoot, evidenceRoot, host, cookieFile] = process.argv.slice(2);
const { chromium } = createRequire(path.join(pluginsRoot, "package.json"))("playwright");
const server = createServer((incoming, outgoing) => {
  const target = new URL(incoming.url, incoming.url.startsWith("/api/") ? host : process.env.EPIC_REVIEW_FRONTEND || "http://frontend");
  const upstream = httpRequest(target, { method: incoming.method, headers: { ...incoming.headers, host: target.host } }, response => {
    outgoing.writeHead(response.statusCode, response.headers); response.pipe(outgoing);
  });
  upstream.on("error", () => { outgoing.writeHead(502); outgoing.end("Review upstream unavailable"); });
  incoming.pipe(upstream);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const cookies = JSON.parse(await readFile(cookieFile, "utf8"));
const report = { real_installed_plugin: true, real_actions_and_database: true, provider_http_fixture: true, checks: [], screenshots: [] };
try {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 1050 } });
    await context.addCookies(cookies.map(cookie => ({ ...cookie, url: origin })));
    const page = await context.newPage();
    const errors = [];
    const requests = [];
    page.on("pageerror", error => errors.push(String(error)));
    page.on("response", async response => {
      if (response.url().includes("/official.epic-games/actions/")) {
        const value = await response.json().catch(() => ({}));
        requests.push({ path: new URL(response.url()).pathname, status: response.status(), ok: value.ok, error: value.error, connected: value.connected, phase: value.phase });
      }
    });
    page.on("dialog", dialog => dialog.accept());
    const mode = width === 390 ? "light" : "dark";
    assert.equal((await context.request.patch(origin + "/api/preferences", { data: { ui_theme: mode, ui_welcome_completed: true } })).status(), 200);
    const destination = `${origin}/plugins/official.epic-games/library`;
    const frame = page.frameLocator("iframe[title='Epic Games Library frontend']");
    await page.goto(destination);
    console.log(JSON.stringify({ width, stage: "opened" }));
    try {
      await frame.locator("#account").filter({ hasText: /Connected as Review player\.|Connect your Epic account to start\./ }).waitFor();
    } catch (error) {
      await page.screenshot({ path: path.join(evidenceRoot, "epic-debug.png"), fullPage: true });
      console.log(JSON.stringify({ url: page.url(), text: await page.locator("body").innerText(), frames: await page.locator("iframe").evaluateAll(items => items.map(item => ({ title: item.title, src: item.src }))), errors }));
      throw error;
    }
    await frame.locator("#signin:enabled").waitFor({ state: "attached" });
    assert.equal(await page.locator("iframe").getAttribute("sandbox"), "allow-scripts");
    if ((await frame.locator("#account").innerText()).startsWith("Connected")) {
      await frame.getByRole("button", { name: "Disconnect Epic", exact: true }).click();
    }
    await frame.getByText("Connect your Epic account to start.", { exact: true }).waitFor();
    await frame.locator("#signin:enabled").waitFor();
    console.log(JSON.stringify({ width, stage: "disconnected", requests }));
    await page.screenshot({ path: path.join(evidenceRoot, `epic-connect-${width}-${mode}.png`), fullPage: true });
    report.screenshots.push(`epic-connect-${width}-${mode}.png`);
    let opened = false;
    await page.route("https://www.epicgames.com/id/login?**", route => {
      opened = true;
      return route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Epic sign-in fixture</title><p>Provider sign-in fixture. No real Epic session is used.</p>" });
    });
    await frame.getByRole("button", { name: "Sign in on Epic Games", exact: true }).click();
    await page.waitForURL("https://www.epicgames.com/id/login?**");
    assert(opened, "A real declared host action navigates outside the opaque frame");
    await page.goBack();
    await frame.getByText("Connect your Epic account to start.", { exact: true }).waitFor();
    await frame.locator("#connect:enabled").waitFor();
    console.log(JSON.stringify({ width, stage: "returned", requests }));
    await frame.getByLabel("Epic authorization code").fill("invalid");
    await frame.getByLabel("Epic authorization code").press("Enter");
    try {
      await frame.getByText("Paste the 32-character authorization code, its JSON page or redirect URL.", { exact: true }).waitFor();
    } catch (error) {
      console.log(JSON.stringify({ stage: "invalid-code", text: await frame.locator("body").innerText(), codeCleared: (await frame.getByLabel("Epic authorization code").inputValue()) === "", disabled: await frame.getByRole("button", { name: "Connect Epic", exact: true }).isDisabled(), buttonType: await frame.locator("#connect").getAttribute("type"), hasNewHandler: (await frame.locator("script").allTextContents()).some(code => code.includes("function connect()")), requests, errors }));
      throw error;
    }
    assert.equal(page.url(), destination, "A failed action stays on the plugin page");
    console.log(JSON.stringify({ width, stage: "invalid-code-passed" }));
    await frame.getByLabel("Epic authorization code").fill("b".repeat(32));
    await frame.getByRole("button", { name: "Connect Epic", exact: true }).click();
    await frame.getByText("Connected as Review player.", { exact: true }).waitFor();
    console.log(JSON.stringify({ width, stage: "connected" }));
    assert.equal(await frame.getByLabel("Epic authorization code").inputValue(), "", "One-time code clears immediately");
    await frame.getByRole("button", { name: "Import games", exact: true }).click();
    await frame.getByRole("button", { name: "Pause after this step", exact: true }).click();
    await frame.locator("#progress").filter({ hasText: "Paused." }).waitFor();
    await page.reload();
    await frame.getByRole("button", { name: "Resume import", exact: true }).click();
    await frame.getByText("Import complete.", { exact: true }).waitFor({ timeout: 90000 });
    assert.equal(await frame.locator("#imported").innerText(), "27");
    assert.equal(await frame.locator("#skipped").innerText(), "1");
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert(await frame.locator("body").evaluate(body => body.scrollWidth <= innerWidth + 1));
    assert.equal(await frame.locator("html").getAttribute("data-theme"), mode);
    await page.screenshot({ path: path.join(evidenceRoot, `epic-complete-${width}-${mode}.png`), fullPage: true });
    report.screenshots.push(`epic-complete-${width}-${mode}.png`);
    assert.deepEqual(errors, []);
    report.checks.push({ width, mode, source_frame_sandbox: "allow-scripts", declared_external_navigation: true,
      code_cleared: true, safe_invalid_code_error: true, pause_reload_resume: true, imported_games: 27, skipped_addons: 1, page_errors: errors, horizontal_overflow: false });
    await context.close();
  }
  await writeFile(path.join(evidenceRoot, "browser-conformance.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
