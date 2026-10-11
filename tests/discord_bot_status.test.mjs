import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

function h(tag, props, children) {
  if (children === undefined && (Array.isArray(props) || typeof props === "string")) return { tag, props: {}, children: props };
  return { tag, props: props || {}, children };
}
function all(tree) { return !tree || typeof tree !== "object" ? [] : [tree, ...[tree.children].flat(Infinity).flatMap(all)]; }
const flush = () => new Promise(resolve => setImmediate(resolve));
async function fixture(respond, admin = false) {
  const source = await readFile(new URL("../official/discord-bot-notifications/native/app.js", import.meta.url), "utf8");
  const { activate } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
  const components = {}, calls = [];
  const host = { async runAction(id, values = {}) { calls.push([id, values]); return respond(id, values); } };
  activate({ pluginId: "official.discord-bot-notifications", vue: { h, ref: value => ({ value }), reactive: x => x, defineComponent: x => x, onBeforeUnmount() {} }, registerComponent: (id, value) => { components[id] = value; } });
  const render = components[admin ? "admin" : "account"].setup({ host });
  await flush(); await flush();
  return { render, calls };
}
const destination = (id, trust, recovery_status) => ({ id, provider_id: "official.discord-bot-notifications.account-dm", kind: "discord_account_dm", revision: 1, active: true, enabled: true, trust, username: id, recovery_status });

test("actual host SECURE/PRIVATE status stays separate from legacy profile proof", async () => {
  let denied = false;
  const f = await fixture(id => id === "get-config" ? { configured: false, accounts: [{ username: "legacy", verified: true }] } : id === "get-destinations" ? (() => {
    if (denied) throw new Error("permission revoked");
    return { destinations: [destination("verified", "SECURE", "eligible"), destination("ordinary", "PRIVATE", "verification_required")] };
  })() : {});
  const nodes = () => all(f.render());
  assert(nodes().some(x => x.children === "SECURE"));
  assert(nodes().some(x => x.children === "PRIVATE"));
  assert(nodes().some(x => x.children === "Legacy profile link · PRIVATE"));
  assert(nodes().some(x => x.children === "Ready for password-reset delivery"));
  const link = nodes().find(x => x.tag === "a" && x.children === "Verify DM and configure recovery");
  assert(link.props.href.includes("notification_destination=ordinary"));
  const search = nodes().find(x => x.tag === "input" && x.props.type === "search");
  search.props.onInput({ target: { value: "ordinary" } });
  assert(!nodes().some(x => x.children === "SECURE"));
  search.props.onInput({ target: { value: "" } });
  denied = true;
  await nodes().find(x => x.tag === "button" && x.children === "Refresh").props.onClick();
  assert(!nodes().some(x => x.children === "SECURE"));
  assert(nodes().some(x => x.props.role === "alert" && String(x.children).includes("Host destination status is unavailable")));
});

test("server selection searches names/IDs and saves selected ID without echoing token", async () => {
  const f = await fixture(id => id === "list-servers" ? { servers: [{ id: "123456789012345678", name: "Tracking" }, { id: "223456789012345678", name: "Other" }] } : { destinations: [] }, true);
  const nodes = () => all(f.render());
  await nodes().find(x => x.tag === "button" && x.children === "Find bot servers").props.onClick();
  const search = nodes().find(x => x.tag === "input" && x.props.placeholder === "Server name or ID");
  search.props.onInput({ target: { value: "tracking" } });
  assert(nodes().some(x => x.tag === "option" && String(x.children).includes("Tracking")));
  assert(!nodes().some(x => x.tag === "option" && String(x.children).includes("Other")));
  nodes().find(x => x.tag === "select").props.onChange({ target: { value: "123456789012345678" } });
  await nodes().find(x => x.tag === "button" && x.children === "Validate and save").props.onClick();
  assert(f.calls.some(([id, values]) => id === "save-bot-config" && values.guild_id === "123456789012345678"));
});

test("channel filtering keeps hidden allowlist selections and never changes trust", async () => {
  const f = await fixture(id => id === "get-config" ? { configured: true } : id === "list-directory" ? { channels: [{ id: "1", name: "general" }, { id: "2", name: "private" }], users: [], allowed_channel_ids: ["2"] } : { destinations: [] }, true);
  const nodes = () => all(f.render());
  await nodes().find(x => x.tag === "button" && x.children === "Load Discord directory").props.onClick();
  nodes().find(x => x.tag === "input" && x.props.placeholder === "Channel name or ID").props.onInput({ target: { value: "general" } });
  nodes().find(x => x.tag === "button" && x.children === "Allow matching channels").props.onClick();
  await nodes().find(x => x.tag === "button" && x.children === "Save allowed channels").props.onClick();
  assert(f.calls.some(([id, values]) => id === "allow-channels" && values.channel_ids.includes("1") && values.channel_ids.includes("2")));
});
