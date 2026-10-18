const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const { buildSync } = require("esbuild");
const { parse, compileScript } = require("@vue/compiler-sfc");

const root = path.resolve(__dirname, "..");
let browser, bundle;
before(async () => {
  const filename = path.join(root, "official/discord-social-activity/ui/GameAttentionList.vue");
  const { descriptor } = parse(fs.readFileSync(filename, "utf8"), { filename });
  const component = compileScript(descriptor, { id: "limits-test", inlineTemplate: true });
  bundle = buildSync({
    stdin: { contents: `import { createApp, h } from "vue";
      ${component.content.replace("export default", "const Attention =")}
      window.actions = [];
      createApp({ render: () => h(Attention, {
        games: [{ key: "title:together", title: "Together", excluded_reasons: ["Confirm player count"],
          requires_player_limits: true, needs_player_limits: true, missing_platforms: [], player_limits: window.savedLimits || null }],
        me: { id: "one", vetoes: [] }, playerCount: 3, platforms: ["PC"],
        onAction: value => window.actions.push(value)
      }) }).mount("#app");`, resolveDir: path.dirname(filename), loader: "js" },
    bundle: true, write: false, format: "iife",
    define: { "process.env.NODE_ENV": '"production"', __VUE_OPTIONS_API__: "false",
      __VUE_PROD_DEVTOOLS__: "false", __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "false" },
  }).outputFiles[0].text;
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
});
after(async () => { await browser?.close(); });

async function editor(savedLimits = null) {
  const page = await browser.newPage();
  await page.setContent('<div id="app"></div>');
  await page.evaluate(value => { window.savedLimits = value; }, savedLimits);
  await page.addScriptTag({ content: bundle });
  await page.locator("summary").click();
  await page.getByRole("button", { name: "Set known player limits", exact: true }).click();
  return page;
}

test("maximum players can be saved with the optional minimum left blank", async () => {
  const page = await editor();
  try {
    await page.getByRole("spinbutton", { name: /^Maximum players/ }).fill("4");
    assert.equal(await page.locator("form").evaluate(form => form.checkValidity()), true);
    await page.getByRole("button", { name: "Save details", exact: true }).click();
    const actions = await page.evaluate(() => window.actions);
    assert.equal(actions.length, 1);
    assert.equal(actions[0].operation, "player-limits");
    assert.equal(actions[0].max_players, 4);
    assert.equal(actions[0].min_players, null);
  } finally { await page.close(); }
});

test("minimum players can be saved with the optional maximum left blank", async () => {
  const page = await editor();
  try {
    await page.getByRole("spinbutton", { name: /^Minimum players/ }).fill("2");
    await page.getByRole("button", { name: "Save details", exact: true }).click();
    assert.deepEqual(await page.evaluate(() => window.actions), [
      { operation: "player-limits", key: "title:together", min_players: 2, max_players: null },
    ]);
  } finally { await page.close(); }
});

test("a saved partial limit remains editable and can become a complete range", async () => {
  const page = await editor({min_players: null, max_players: 4, confirmed_by: "one"});
  try {
    assert.match(await page.locator("form").innerText(), /Up to 4 players · minimum unknown/);
    assert.equal(await page.getByRole("spinbutton", { name: /^Maximum players/ }).inputValue(), "4");
    await page.getByRole("spinbutton", { name: /^Minimum players/ }).fill("2");
    await page.getByRole("button", { name: "Save details", exact: true }).click();
    assert.deepEqual(await page.evaluate(() => window.actions), [
      { operation: "player-limits", key: "title:together", min_players: 2, max_players: 4 },
    ]);
  } finally { await page.close(); }
});

test("clearing an entered minimum keeps it unknown when saving a maximum", async () => {
  const page = await editor();
  try {
    await page.getByRole("spinbutton", { name: /^Minimum players/ }).fill("2");
    await page.getByRole("spinbutton", { name: /^Minimum players/ }).fill("");
    await page.getByRole("spinbutton", { name: /^Maximum players/ }).fill("4");
    await page.getByRole("button", { name: "Save details", exact: true }).click();
    const actions = await page.evaluate(() => window.actions);
    assert.equal(actions[0].min_players, null);
    assert.equal(actions[0].max_players, 4);
  } finally { await page.close(); }
});

test("leaving both player limits blank approves only the current group", async () => {
  const page = await editor();
  try {
    await page.getByRole("button", { name: "Save details", exact: true }).click();
    assert.deepEqual(await page.evaluate(() => window.actions), [
      { operation: "approve-group", keys: ["title:together"] },
    ]);
  } finally { await page.close(); }
});

test("a supplied minimum above the maximum still blocks submission", async () => {
  const page = await editor();
  try {
    await page.getByRole("spinbutton", { name: /^Minimum players/ }).fill("5");
    await page.getByRole("spinbutton", { name: /^Maximum players/ }).fill("4");
    assert.equal(await page.locator("form").evaluate(form => form.checkValidity()), false);
    await page.getByRole("button", { name: "Save details", exact: true }).click();
    assert.deepEqual(await page.evaluate(() => window.actions), []);
  } finally { await page.close(); }
});
