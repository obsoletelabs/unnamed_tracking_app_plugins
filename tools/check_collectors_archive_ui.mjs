// Run only against a disposable host with the official archive installed.
// All records and sessions use the authenticated public HTTP/plugin APIs.
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { createServer, request as httpRequest } from "node:http";
import { createRequire } from "node:module";
import path from "node:path";

const [hostArgument, outputArgument, backend, cookieFile] =
  process.argv.slice(2);
assert.ok(
  cookieFile,
  "Usage: check_collectors_archive_ui.mjs <host> <output> <backend> <temporary-admin-cookies>",
);
const host = path.resolve(hostArgument),
  output = path.resolve(outputArgument);
await mkdir(output, { recursive: true });
const frontend = path.join(host, "src/frontend/dist");
const require = createRequire(new URL("../package.json", import.meta.url));
const { chromium } = require("playwright");
const server = createServer(async (incoming, outgoing) => {
  if (incoming.url.startsWith("/api/")) {
    const upstream = httpRequest(
      new URL(incoming.url, backend),
      {
        method: incoming.method,
        headers: { ...incoming.headers, host: new URL(backend).host },
      },
      (response) => {
        outgoing.writeHead(response.statusCode, response.headers);
        response.pipe(outgoing);
      },
    );
    upstream.on("error", () => {
      outgoing.writeHead(502);
      outgoing.end("Host unavailable");
    });
    incoming.pipe(upstream);
    return;
  }
  let relative = decodeURIComponent(
    new URL(incoming.url, "http://localhost").pathname,
  ).replace(/^\//, "");
  if (!relative.startsWith("assets/")) relative = "index.html";
  const file = path.resolve(frontend, relative);
  if (!file.startsWith(frontend + path.sep)) {
    outgoing.writeHead(403);
    outgoing.end();
    return;
  }
  try {
    outgoing.setHeader(
      "Content-Type",
      {
        ".js": "text/javascript",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".html": "text/html",
      }[path.extname(file)] ?? "application/octet-stream",
    );
    outgoing.end(await readFile(file));
  } catch {
    outgoing.writeHead(404);
    outgoing.end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin =
  process.env.COLLECTOR_FRONTEND_ORIGIN ??
  `http://127.0.0.1:${server.address().port}`;
if (process.env.COLLECTOR_FRONTEND_ORIGIN)
  assert.equal(new URL(origin).origin, new URL(backend).origin);
const plugin = "official.collectors-archive",
  users = [],
  disabled = [];
const report = {
  kind: process.env.COLLECTOR_FRONTEND_ORIGIN
    ? "authenticated-production-host"
    : "authenticated-real-host",
  passed: [],
  captures: [],
  status: "running",
};
if (process.env.COLLECTOR_PACKAGE_SHA256)
  report.package_sha256 = process.env.COLLECTOR_PACKAGE_SHA256;
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
const admin = await browser.newContext();
const cookies = JSON.parse(await readFile(cookieFile, "utf8"));
await admin.addCookies(
  cookies.map(({ name, value }) => ({ name, value, url: origin })),
);
let reviewPage;
let archiveDisabled = false;
const contexts = [],
  errors = [];
const checkpoint = (message) => {
  report.passed.push(message);
  console.log(message);
};
async function http(context, method, route, data, expected = 200) {
  const response = await context.request.fetch(origin + "/api" + route, {
    method,
    ...(data === undefined ? {} : { data }),
  });
  const detail =
    response.status() !== expected && route.startsWith(`/plugins/${plugin}/`)
      ? await response.text()
      : "";
  assert.equal(
    response.status(),
    expected,
    `${method} ${route}: HTTP ${response.status()} ${detail}`,
  );
  return expected === 204 ? null : response.json();
}
async function action(context, id, values = {}) {
  return http(context, "POST", `/plugins/${plugin}/actions/${id}`, { values });
}
async function archive(context, method, route, body = {}, expected = 200) {
  const result = await action(context, "api", { method, path: route, body });
  assert.equal(
    result.status_code,
    expected,
    `${method} ${route}: ${JSON.stringify(result.body)}`,
  );
  return result.body;
}
async function imported(context) {
  for (const table of [
    "sets",
    "bounties",
    "cards",
    "bounty_objectives",
    "bounty_evidence",
    "bounty_journal_entries",
    "bounty_point_transactions",
  ]) {
    const result = await action(context, "import-legacy", { table });
    assert.equal(
      result.complete,
      true,
      "New account imports must be empty and complete",
    );
  }
  assert.equal((await action(context, "migration-status")).imported, true);
}
try {
  assert.equal((await http(admin, "GET", "/auth/me")).is_admin, true);
  const installations = await http(admin, "GET", "/plugins");
  assert.equal(
    installations.find((item) => item.plugin_id === plugin)?.status,
    "running",
  );
  for (const id of [
    "example.help-button",
    "example.ui-playground",
    "example.shortcut-playground",
  ]) {
    if (installations.find((item) => item.plugin_id === id)?.enabled) {
      await http(admin, "POST", `/plugins/${id}/disable`);
      disabled.push(id);
    }
  }
  for (let index = 0; index < 2; index++) {
    const username = "collector-review-" + randomBytes(6).toString("hex");
    const password = randomBytes(18).toString("hex") + "-A1!";
    const user = await http(
      admin,
      "POST",
      "/auth/users",
      { username, email: username + "@example.invalid", password },
      201,
    );
    users.push(user.id);
    const context = await browser.newContext();
    contexts.push(context);
    await http(context, "POST", "/auth/login", {
      username_or_email: username,
      password,
    });
    await http(context, "PATCH", "/preferences", {
      ui_welcome_completed: true,
    });
    await imported(context);
  }
  const [owner, other] = contexts;
  const game = await http(
    owner,
    "POST",
    "/game/create",
    {
      title: "First Archive Quest",
      folder_location: "collector-review-" + randomBytes(6).toString("hex"),
      status: "MASTERED",
      collections: ["Archive classics"],
    },
    201,
  );
  const bounty = (
    await archive(
      owner,
      "POST",
      "bounties",
      {
        title: "Archive objective check",
        type: "custom",
        points_reward: 75,
        target_date: Math.floor(Date.now() / 1000) + 2 * 86400,
      },
      201,
    )
  ).bounty;
  const objective = (
    await archive(owner, "POST", `bounties/${bounty.id}/objectives`, {
      title: "Check the archive",
      kind: "checkbox",
    })
  ).objective;
  await archive(
    owner,
    "PATCH",
    `bounties/${bounty.id}/objectives/${objective.id}`,
    { done: true },
  );
  await archive(owner, "POST", `bounties/${bounty.id}/evidence`, {
    kind: "note",
    text: "Verified through the installed plugin",
  });
  await archive(owner, "POST", `bounties/${bounty.id}/journal`, {
    text: "The archive is intact",
  });
  const paid = (
    await archive(
      owner,
      "POST",
      "bounties",
      { title: "Completed archive check", type: "custom", points_reward: 75 },
      201,
    )
  ).bounty;
  await archive(owner, "POST", `bounties/${paid.id}/complete`);
  assert.equal(
    (await archive(owner, "GET", "bounties/points/total")).total,
    150,
  );
  await archive(owner, "POST", `bounties/${paid.id}/complete`);
  assert.equal(
    (await archive(owner, "GET", "bounties/points/total")).total,
    150,
  );
  assert.equal(
    (await archive(owner, "GET", `bounties/${bounty.id}`)).bounty.status,
    "completed",
  );
  await archive(
    owner,
    "POST",
    "bounties",
    {
      title: "Archive deadline quest",
      type: "custom",
      target_date: Math.floor(Date.now() / 1000) + 2 * 86400,
    },
    201,
  );
  await archive(other, "GET", `bounties/${bounty.id}`, {}, 404);
  checkpoint(
    "New-account import, bounty objectives/evidence/journal, idempotent rewards and cross-user denial pass through the installed worker",
  );
  const page = await owner.newPage();
  reviewPage = page;
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto(origin + `/plugins/${plugin}/sets`);
  await page.getByRole("heading", { name: "Sets", exact: true }).waitFor();
  await page
    .getByRole("textbox", { name: "New set name", exact: true })
    .fill("First classics");
  await page
    .getByRole("spinbutton", {
      name: "Expected card total (optional)",
      exact: true,
    })
    .fill("1");
  await page.getByRole("button", { name: "+ Create Set", exact: true }).click();
  await page
    .getByRole("heading", { name: "First classics", exact: true })
    .waitFor();
  const savedSet = (await archive(owner, "GET", "sets")).find(
    (item) => item.name === "First classics",
  );
  assert.ok(savedSet);
  await page.goto(origin + `/plugins/${plugin}/cards`);
  await page.getByRole("heading", { name: "Cards", exact: true }).waitFor();
  await page.getByRole("button", { name: "New card", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "New card", exact: true });
  await picker
    .getByRole("textbox", { name: "Search eligible games" })
    .fill("First Archive");
  await picker.getByRole("button", { name: "Create", exact: true }).click();
  await page.waitForURL(
    new RegExp(`/plugins/${plugin}/card-detail\\?record_id=`),
  );
  await page.getByRole("heading", { name: /^First Archive Quest/ }).waitFor();
  const card = (await archive(owner, "GET", "cards")).find(
    (item) => item.game_id === game.id,
  );
  assert.ok(card);
  await archive(owner, "PATCH", `cards/${card.id}`, {
    set_id: savedSet.id,
    rarity: "mythic",
  });
  assert.equal(
    (await archive(owner, "GET", `sets/${savedSet.id}`)).is_complete,
    true,
  );
  await archive(other, "GET", `cards/${card.id}`, {}, 404);
  await archive(other, "GET", `sets/${savedSet.id}`, {}, 404);
  await archive(owner, "POST", `cards/${card.id}/prestige-challenge`, {}, 400);
  checkpoint(
    "Native set creation and searched game-card picker persist real records; completed sets, edits, ownership and prestige prerequisites pass",
  );
  const routes = [
    ["cards", "Cards"],
    [`card-detail?record_id=${card.id}`, /^First Archive Quest/],
    ["sets", "Sets"],
    [`set-detail?record_id=${savedSet.id}`, "First classics"],
    ["bounties", "Bounties"],
    ["migration", "Collector's Archive"],
  ];
  for (const [width, theme] of [
    [320, "light"],
    [390, "dark"],
    [1440, "light"],
    [1920, "dark"],
  ]) {
    await page.setViewportSize({ width, height: width < 500 ? 800 : 1050 });
    await http(owner, "PATCH", "/preferences", { ui_theme: theme });
    for (const [route, title] of routes) {
      await page.goto(origin + `/plugins/${plugin}/` + route);
      await page
        .getByRole("heading", { name: title, exact: typeof title === "string" })
        .first()
        .waitFor();
      await page
        .getByText(/^Loading(?:\.{3}|…)?$/)
        .first()
        .waitFor({ state: "hidden", timeout: 60000 });
      assert.equal(
        await page
          .locator(".collector-error:visible, .empty-state.error:visible")
          .count(),
        0,
      );
      if (route === "cards")
        await page
          .getByText("First Archive Quest", { exact: true })
          .first()
          .waitFor();
      if (route === "sets")
        await page
          .getByRole("heading", { name: "First classics", exact: true })
          .waitFor();
      if (route === "bounties") {
        await page.getByLabel("Search bounties").waitFor({ timeout: 60000 });
        await page.getByLabel("Search bounties").fill("Archive deadline quest");
      }
      assert.equal(
        await page.evaluate(() => document.documentElement.dataset.theme),
        theme,
      );
      const dimensions = await page.evaluate(() => ({
        width: innerWidth,
        scroll: document.documentElement.scrollWidth,
        sidebarScroll: document.querySelector(".nav-scroll")?.scrollWidth,
        sidebarClient: document.querySelector(".nav-scroll")?.clientWidth,
      }));
      assert.ok(
        dimensions.scroll <= dimensions.width + 1,
        route + " overflow: " + JSON.stringify(dimensions),
      );
      if (dimensions.sidebarClient)
        assert.ok(
          dimensions.sidebarScroll <= dimensions.sidebarClient + 1,
          "Sidebar overflow",
        );
      assert.ok(
        width <= 760 || dimensions.sidebarClient > 0,
        "Measured desktop sidebar is required",
      );
      await page.evaluate(() => window.scrollTo(0, 0));
      const filename = `collector-loaded-${route.split("?")[0]}-${width}-${theme}.png`;
      await page.screenshot({
        path: path.join(output, filename),
        fullPage: false,
      });
      report.captures.push({
        filename,
        route: route.split("?")[0],
        width,
        theme,
      });
    }
    checkpoint(
      `Six loaded native pages, theme and viewport/side-navigation overflow pass at ${width}/${theme}`,
    );
  }
  await page.setViewportSize({ width: 1440, height: 1050 });
  await http(owner, "PATCH", "/preferences", {
    home_widgets: [`plugin:${plugin}:goals`],
  });
  await page.goto(origin + "/");
  const goals = page.getByRole("region", {
    name: "Goals & bounties",
    exact: true,
  });
  await goals
    .getByRole("link", { name: "Archive deadline quest", exact: true })
    .waitFor({ timeout: 60000 });
  await goals.getByText("150", { exact: true }).waitFor();
  await page.keyboard.press("Control+k");
  const command = page.getByRole("dialog", {
    name: "Search library",
    exact: true,
  });
  await command
    .getByLabel("Search library", { exact: true })
    .fill("Archive deadline quest");
  await command
    .getByText("Archive deadline quest", { exact: true })
    .first()
    .waitFor();
  await page.keyboard.press("Escape");
  checkpoint(
    "The installed native search provider contributes a real bounty to global Ctrl+K results",
  );
  await page.screenshot({
    path: path.join(output, "collector-home-loaded-1440-dark.png"),
    fullPage: false,
  });
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .first()
    .click();
  const reminders = page.getByRole("region", {
    name: "Recent notifications",
    exact: true,
  });
  await reminders
    .getByText("Archive deadline quest", { exact: true })
    .waitFor({ timeout: 60000 });
  await reminders.getByText("Archive deadline quest", { exact: true }).click();
  await page.waitForURL(new RegExp(`/plugins/${plugin}/bounties\\?record_id=`));
  await page.getByLabel("Search bounties").waitFor({ timeout: 60000 });
  await page.waitForFunction(
    (field) => field.value === "Archive deadline quest",
    await page.getByLabel("Search bounties").elementHandle(),
    { timeout: 60000 },
  );
  assert.equal(
    await page.getByLabel("Search bounties").inputValue(),
    "Archive deadline quest",
  );
  checkpoint(
    "Home goals show real records and earned points; a deadline reminder opens the exact bounty",
  );
  // Hold a background suggestion across disable to exercise page teardown
  // while an installed worker request is still in flight.
  let releaseSuggestion;
  const heldSuggestion = new Promise(resolve => { releaseSuggestion = resolve; });
  let suggestionRequests = 0;
  const actionRoute = `**/api/plugins/${plugin}/actions/api`;
  const isSuggestion = request => request.postDataJSON()?.values?.path === "bounties/random";
  await page.route(actionRoute, async route => {
    if (isSuggestion(route.request())) {
      suggestionRequests++;
      if (suggestionRequests === 1) await heldSuggestion;
    }
    await route.continue();
  });
  const suggestionStarted = page.waitForRequest(isSuggestion);
  await page.reload({ waitUntil: "domcontentloaded" });
  await suggestionStarted;
  await http(admin, "POST", `/plugins/${plugin}/disable`);
  archiveDisabled = true;
  releaseSuggestion();
  await page.goto(origin + "/");
  await page.locator(".archive-goals").waitFor({ state: "hidden" });
  await page.locator(".widget-unavailable").waitFor();
  assert.equal(suggestionRequests, 1, "Closed pages must stop scheduling suggestion requests");
  await page.unroute(actionRoute);
  await http(admin, "POST", `/plugins/${plugin}/enable`);
  archiveDisabled = false;
  await page.reload();
  await page
    .locator(".archive-goals")
    .getByRole("link", { name: "Archive deadline quest", exact: true })
    .waitFor({ timeout: 60000 });
  checkpoint(
    "Disabling the installed archive removes its live Home component; re-enabling restores the same owned records",
  );
  assert.deepEqual(errors, []);
  report.status = "passed";
  await writeFile(
    path.join(output, "collector-ui-conformance.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
} catch (error) {
  if (reviewPage) {
    await reviewPage.screenshot({
      path: path.join(output, "collector-ui-private-failure.png"),
    });
    console.error("Native browser exceptions:", errors);
    console.error(
      (await reviewPage.locator("body").innerText()).slice(0, 3500),
    );
  }
  report.status = "failed";
  await writeFile(
    path.join(output, "collector-ui-conformance.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
  throw error;
} finally {
  if (archiveDisabled) await http(admin, "POST", `/plugins/${plugin}/enable`);
  for (const id of users.reverse())
    await http(admin, "DELETE", `/auth/users/${id}`);
  for (const id of disabled) await http(admin, "POST", `/plugins/${id}/enable`);
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
