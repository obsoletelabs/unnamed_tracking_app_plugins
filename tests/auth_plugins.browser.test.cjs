const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

let browser;
before(async () => { browser = await chromium.launch({ args: ["--no-sandbox"] }); });
after(async () => { await browser?.close(); });

function markup(slug) {
  const root = path.resolve(__dirname, `../official/${slug}/frontend`);
  const asset = name => fs.readFileSync(name.startsWith("appearance.")
    ? path.resolve(__dirname, `../sdk/frontend_${name}`) : path.join(root, name), "utf8");
  return fs.readFileSync(path.join(root, "index.html"), "utf8")
    .replace(/<link rel="stylesheet" href="\.\/([^"]+)">/g, (_, name) => `<style>${asset(name)}</style>`)
    .replace(/<script src="\.\/([^"]+)"(?: defer)?><\/script>/g,
      (_, name) => `<script nonce="fixture">${asset(name).replace(/<\/script/gi, "<\\/script")}</script>`)
    .replace("<head>", '<head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'nonce-fixture\'; style-src \'unsafe-inline\'">');
}

async function mount(page, slug, { registered = false, invite = false } = {}) {
  await page.route("https://fixture.test/**", route => route.fulfill({ contentType: "text/html", body: markup(slug) }));
  await page.setContent('<iframe sandbox="allow-scripts" style="width:100%;height:1800px;border:0"></iframe>');
  await page.evaluate(({ slug, registered, invite }) => {
    const iframe = document.querySelector("iframe");
    window.dispatched = [];
    window.cancelDisable = false;
    window.fixtureState = {
      registered, token_lifetime_seconds: slug === "user-invites" ? 86400 : 1200,
      sender_name: "", email_subject: "You are invited", email_heading: "Join our library",
      welcome_message: "You have been invited to create an account.", greeting: "personal",
      button_label: "Accept invitation", email_layout: "card", accent_color: "#3458d4",
      footer_message: "Sent by your tracking app.",
    };
    window.addEventListener("message", event => {
      if (event.source !== iframe.contentWindow || event.data?.type !== "plugin-api-request") return;
      const { method, requestId, payload } = event.data;
      let result = {};
      if (method === "plugin.run-action") {
        const { actionId, values } = payload;
        if (actionId === "disable" && window.cancelDisable) result = { cancelled: true };
        else {
          window.dispatched.push({ actionId, values });
          if (actionId === "status") result = { ...window.fixtureState };
          if (actionId === "save") Object.assign(window.fixtureState, values);
          if (actionId === "enable") window.fixtureState.registered = true;
          if (actionId === "disable") window.fixtureState.registered = false;
          if (actionId === "list-invites") result = { invitations: [] };
        }
      }
      event.source.postMessage({ type: "plugin-api-response", requestId, result }, "*");
    });
    iframe.src = `https://fixture.test/frontend?page=${invite ? "invite" : "configure"}`;
  }, { slug, registered, invite });
  const frame = page.frameLocator("iframe");
  await frame.getByRole("button", { name: invite ? "Send invitation" : slug === "user-invites" ? "Save invitation settings" : "Save recovery settings", exact: true }).waitFor();
  await frame.locator(invite ? "#issue" : "#save").evaluate(element => new Promise(resolve => {
    const timer = setInterval(() => { if (!element.disabled) { clearInterval(timer); resolve(); } }, 10);
  }));
  return frame;
}

test("invitation settings convert readable time units without enabling the flow", async () => {
  const page = await browser.newPage();
  try {
    const frame = await mount(page, "user-invites");
    for (const [amount, unit, seconds] of [[60, "60", 3600], [24, "3600", 86400], [2, "86400", 172800], [1, "604800", 604800]]) {
      await frame.locator("#lifetime").fill(String(amount));
      await frame.locator("#unit").selectOption(unit);
      await frame.getByRole("button", { name: "Save invitation settings" }).click();
      await frame.getByText("Invitation settings saved.", { exact: true }).waitFor();
      assert.equal(await page.evaluate(() => window.fixtureState.token_lifetime_seconds), seconds);
      assert.equal(await page.evaluate(() => window.fixtureState.registered), false);
    }
    const before = await page.evaluate(() => window.dispatched.filter(action => action.actionId === "save").length);
    await frame.locator("#lifetime").fill("2");
    await frame.locator("#unit").selectOption("604800");
    await frame.getByRole("button", { name: "Save invitation settings" }).click();
    await frame.getByText("Choose an invitation lifetime between 1 hour and 1 week.").waitFor();
    assert.equal(await page.evaluate(() => window.dispatched.filter(action => action.actionId === "save").length), before);
  } finally { await page.close(); }
});

test("email previews render administrator wording as text and preserve customization on save", async () => {
  const page = await browser.newPage();
  try {
    const frame = await mount(page, "user-invites");
    await frame.getByText("Email appearance and wording", { exact: true }).click();
    await frame.locator("#sender_name").fill("Library team");
    await frame.locator("#welcome_message").fill('<img src=x onerror="alert(1)"> Welcome, friend!');
    await frame.locator("#greeting").selectOption("none");
    await frame.locator("#email_layout").selectOption("simple");
    assert.equal(await frame.locator("#preview-welcome").innerText(), '<img src=x onerror="alert(1)"> Welcome, friend!');
    assert.equal(await frame.locator("#preview img").count(), 0);
    assert.equal(await frame.locator("#preview-greeting").innerText(), "");
    await frame.getByRole("button", { name: "Save invitation settings" }).click();
    await frame.getByText("Invitation settings saved.", { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.fixtureState.sender_name), "Library team");
    assert.equal(await page.evaluate(() => window.fixtureState.email_layout), "simple");
  } finally { await page.close(); }
});

test("cancelled disable leaves the enabled flow and controls unchanged", async () => {
  for (const slug of ["user-invites", "password-reset"]) {
    const page = await browser.newPage();
    try {
      const frame = await mount(page, slug, { registered: true });
      await page.evaluate(() => { window.cancelDisable = true; });
      await frame.locator("#disable").click();
      await frame.locator("#disable").evaluate(element => new Promise(resolve => {
        const timer = setInterval(() => { if (!element.disabled) { clearInterval(timer); resolve(); } }, 10);
      }));
      assert.equal(await page.evaluate(() => window.fixtureState.registered), true);
      assert.equal(await page.evaluate(() => window.dispatched.some(action => action.actionId === "disable")), false);
      assert.equal(await frame.locator("#feedback").innerText(), "");
    } finally { await page.close(); }
  }
});

test("the invite dialog forwards an optional recipient name and clears delivered input", async () => {
  const page = await browser.newPage();
  try {
    const frame = await mount(page, "user-invites", { registered: true, invite: true });
    await frame.locator("#email").fill("alex@example.invalid");
    await frame.locator("#recipient_name").fill("  Alex  ");
    await frame.locator("#recipient_name").press("Enter");
    await frame.getByText("Invitation queued. Check delivery below.", { exact: true }).waitFor();
    assert.deepEqual(await page.evaluate(() => window.dispatched.find(action => action.actionId === "issue").values), {
      email: "alex@example.invalid", recipient_name: "Alex",
    });
    assert.equal(await frame.locator("#email").inputValue(), "");
    assert.equal(await frame.locator("#recipient_name").inputValue(), "");
  } finally { await page.close(); }
});

test("recovery uses hours without changing activation and both settings fit small screens", async () => {
  for (const width of [320, 390, 1440]) {
    for (const slug of ["user-invites", "password-reset"]) {
      const page = await browser.newPage({ viewport: { width, height: 1100 } });
      try {
        const frame = await mount(page, slug);
        if (slug === "password-reset") {
          await frame.locator("#lifetime").fill("1");
          await frame.locator("#unit").selectOption("3600");
          await frame.locator("#save").click();
          await frame.getByText("Recovery settings saved.", { exact: true }).waitFor();
          assert.equal(await page.evaluate(() => window.fixtureState.token_lifetime_seconds), 3600);
          assert.equal(await page.evaluate(() => window.fixtureState.registered), false);
        } else await frame.getByText("Email appearance and wording", { exact: true }).click();
        assert(await frame.locator("body").evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      } finally { await page.close(); }
    }
  }
});
